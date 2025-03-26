"""Handles the different validation strategies for a request or chained request."""

from __future__ import annotations
import abc
import functools
import logging
import operator
import sys
from tools import settings


def _get_logger() -> logging.Logger:
    """
    Get the logger for the module inspecting the runtime environment.
    """
    entry_script_name = sys.argv[0].split("/")[-1]
    if entry_script_name == "main.py":
        # Running the web application service.
        return logging.getLogger("mcm_error")
    else:
        return logging.getLogger()

logger = _get_logger()


class ValidationStrategy(abc.ABC):
    """Determine how to submit validations and compute its number of events."""

    def __init__(self):
        self.logger = logger

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        pass

    @abc.abstractmethod
    def move_validation_to_next_stage(self, validation_control, validation_name):
        """
        Move a validation to the next stage submitting multicore jobs.

        Args:
            validation_control (ValidationControl): Controller for handling validations.
            validation_name (str): Validation to process.
        """
        pass

    @abc.abstractmethod
    def get_event_count_for_validation(self, request, with_explanation=False, threads=None) -> int | tuple[int, str]:
        """
        Get the number of events to run in a validation job with an
        optional explanation about how the value is computated.

        Args:
            request (json_layer.request.request): Request to which validation events will be counted.
            with_explanation (bool): Enables returning a explanation about how the count was calculated.
            threads (int | None): Number of threads for the validation job. If None, it
                is assumed it is related to int(1) thread.

        Returns:
            The number of validation events with an optional explanation
                about how the value was calculated.
        """
        pass

    @abc.abstractmethod
    def submit_initial_validation(self, validation_control, validation_name):
        """
        Submit the initial validation job for a strategy.

        Args:
            validation_control (ValidationControl): Controller for handling validations.
            validation_name (str): Validation to process.
        """
        pass

    def get_validation_max_runtime(self, request) -> int:
        """
        Get the maximum number of seconds that a job could run.

        Args:
            request (json_layer.request.request): Request to compute validation runtime.

        Returns:
            Maximum runtime in seconds for a validation job.
        """
        multiplier = request.get_attribute('validation').get('time_multiplier', 1)
        max_runtime = settings.get_value('batch_timeout') * 60. * multiplier
        return max_runtime

    def tweak_cmsdriver_for_validation(self, request, sequence_dict, threads) -> dict:
        """
        Tweak the cmsDriver command dictionary related to a sequence
        and include extra parameters if required.

        Args:
            request (json_layer.request.request): Request to tweak the setup script.
            sequence_dict (dict): Parameters for building the cmsDriver command
                for a sequence.
            threads (int | None): Number of threads for the validation job. If None, it
                is assumed it is related to int(1) thread.

        Returns:
            Parameters for building the cmsDriver command for a sequence.
        """
        return sequence_dict


class LongValidationStrategy(ValidationStrategy):
    @classmethod
    def name(cls) -> str:
        return "LONG"

    def submit_initial_validation(self, validation_control, validation_name):
        validation_control.submit_item(validation_name, 1)

    def move_validation_to_next_stage(self, validation_control, validation_name):
        validation_control.submit_item(validation_name, 2)
        validation_control.submit_item(validation_name, 4)
        validation_control.submit_item(validation_name, 8)

    def get_event_count_for_validation(self, request, with_explanation=False, threads=None) -> int | tuple[int, str]:
        # Efficiency
        efficiency = request.get_efficiency()
        # Max number of events to run
        max_events = request.target_for_test()
        # Max events taking efficiency in consideration
        max_events_with_eff = max_events / efficiency
        # Max number of seconds that validation can run for
        max_runtime = self.get_validation_max_runtime(request=request)
        # "Safe" margin of validation that will not be used for actual running
        # but as a buffer in case user given time per event is slightly off
        margin = settings.get_value('test_timeout_fraction')
        # Time per event
        time_per_event = request.get_attribute('time_event')
        # Threads in sequences
        sequence_threads = [int(sequence.get('nThreads', 1)) for sequence in request.get_attribute('sequences')]
        while len(sequence_threads) < len(time_per_event):
            time_per_event = time_per_event[:-1]

        # Time per event for single thread
        single_thread_time_per_event = [time_per_event[i] * sequence_threads[i] for i in range(len(time_per_event))]
        # Sum of single thread time per events
        time_per_event_sum = sum(single_thread_time_per_event)
        # Max runtime with applied margin
        max_runtime_with_margin = max_runtime * (1.0 - margin)
        # How many events can be produced in given "safe" time
        events = int(max_runtime_with_margin / time_per_event_sum)
        # Try to produce at least one event
        clamped_events = int(max(1, min(events, max_events_with_eff)))
        # Estimate produced events
        estimate_produced = int(clamped_events * efficiency)

        self.logger.info('Events to run for %s - %s', request.get_attribute('prepid'), clamped_events)
        if not with_explanation:
            return clamped_events
        else:
            explanation = ['# Maximum validation duration: %ds' % (max_runtime),
                           '# Margin for validation duration: %d%%' % (margin * 100),
                           '# Validation duration with margin: %d * (1 - %.2f) = %ds' % (max_runtime, margin, max_runtime_with_margin),
                           '# Time per event for each sequence: %s' % (', '.join(['%.4fs' % (x) for x in time_per_event])),
                           '# Threads for each sequence: %s' % (', '.join(['%s' % (x) for x in sequence_threads])),
                           '# Time per event for single thread for each sequence: %s' % (', '.join(['%s * %.4fs = %.4fs' % (sequence_threads[i], time_per_event[i], single_thread_time_per_event[i]) for i in range(len(single_thread_time_per_event))])),
                           '# Which adds up to %.4fs per event' % (time_per_event_sum),
                           '# Single core events that fit in validation duration: %ds / %.4fs = %d' % (max_runtime_with_margin, time_per_event_sum, events),
                           '# Produced events limit in McM is %d' % (max_events),
                           '# According to %.4f efficiency, validation should run %d / %.4f = %d events to reach the limit of %s' % (efficiency, max_events, efficiency, max_events_with_eff, max_events),
                           '# Take the minimum of %d and %d, but more than 0 -> %d' % (events, max_events_with_eff, clamped_events),
                           '# It is estimated that this validation will produce: %d * %.4f = %d events' % (clamped_events, efficiency, estimate_produced)]
            return clamped_events, '\n'.join(explanation)

    def tweak_cmsdriver_for_validation(self, request, sequence_dict, threads) -> dict:
        threads_int = threads if isinstance(threads, int) else 1
        input_events = self.get_event_count_for_validation(request=request, threads=threads)

        # Set the number of event parameters
        sequence_dict["nThreads"] = threads_int
        sequence_dict["number"] = input_events # -n
        return sequence_dict


class ShortValidationStrategy(ValidationStrategy):
    @classmethod
    def name(cls) -> str:
        return "SHORT"

    def submit_initial_validation(self, validation_control, validation_name):
        # Pick the thread configuration for all requests
        # then pick the number of threads removing duplicates
        requests = validation_control.requests_for_validation(validation_name)
        thread_config_requests = [
            self._get_thread_configurations(request=request)
            for request in requests
        ]
        threads_to_run = {int(key) for thread_config in thread_config_requests for key in thread_config.keys()}
        min_thread_int = min(threads_to_run)
        validation_control.submit_item(validation_name, min_thread_int)

    def move_validation_to_next_stage(self, validation_control, validation_name):
        # Pick the thread configuration for all requests
        # then pick the number of threads removing duplicates
        requests = validation_control.requests_for_validation(validation_name)
        thread_config_requests = [
            self._get_thread_configurations(request=request)
            for request in requests
        ]
        threads_to_run = {int(key) for thread_config in thread_config_requests for key in thread_config.keys()}

        # Discard the minimum as it was already sent
        threads_to_run.discard(min(threads_to_run))
        for threads_int in threads_to_run:
            validation_control.submit_item(validation_name, threads_int)

    def get_event_count_for_validation(self, request, with_explanation=False, threads=None) -> int | tuple[int, str]:
        threads_int = threads if isinstance(threads, int) else 1
        threads_str = str(threads_int)
        # Run the validation job based on output events
        test_on_output = self._test_on_output_events()
        # Validation scenarios
        validation_thread_configurations = self._get_thread_configurations(request=request)
        thread_config = validation_thread_configurations.get(threads_str)
        if not thread_config:
            self.logger.error("Unable to retrieve the validation scenario for %s threads", threads_str)
            raise RuntimeError("Unable to retrieve the validation scenario for %s threads" % (threads_str))

        target_input_events = thread_config["target_input_events"]
        if not with_explanation:
            return target_input_events

        explanation = [
            "# Maximum validation runtime: %ds" % (thread_config["maximum_runtime"]),
            "# Minimum validation runtime: %ds" % (thread_config["minimum_runtime"]),
            "# Output events for the validation job: %d" % (thread_config["output_events"]),
            "# Event efficiency: Computed using `filter_efficiency` * `match_efficiency` using the latest generator parameters",
            "# Event efficiency: Set to 1 in case the result ends up being zero",
            "# Event efficiency: %.4f" % (thread_config["event_efficiency"]),
            "# Time per event: Computed multiplying all the time_per_event values on every sequence",
            "# Time per event: Set to 1 in case the result ends up being zero",
            "# Time per event: %.4f" % (thread_config["time_per_event"]),
            "# Input events: Computed using `int(output_events / event_efficiency)` - int(%d / %.4f): %d" % (
                thread_config["output_events"],
                thread_config["event_efficiency"],
                thread_config["input_events"],
            ),
        ]

        # Check if the target input or target output events were modified.
        truncated = thread_config["truncated"]
        extended = thread_config["extended"]
        target_events_explanation = []
        if truncated or extended:
            target_events_explanation += [
                "# Initial target input events: %d" % (thread_config["input_events"]),
                "# Initial target output events: %d" % (thread_config["output_events"]),
            ]
            if truncated:
                target_events_explanation += [
                    "# Target input and output events were modified so that the validation runs in the expected maximum runtime."
                ]
            if extended:
                target_events_explanation += [
                    "# Target input and output events were modified so that the validation runs at least the minimum expected runtime."
                ]

        # Final target values
        target_events_explanation += [
            "# Target input events: %d" % (thread_config["target_input_events"]),
            "# Target output events: %d" % (thread_config["target_output_events"])
        ]
        explanation += target_events_explanation

        if test_on_output:
            explanation += [
                "# INFO: This validation will be computed based on the number of target output events!"
            ]

        return target_input_events, '\n'.join(explanation)

    def tweak_cmsdriver_for_validation(self, request, sequence_dict, threads) -> dict:
        threads_int = threads if isinstance(threads, int) else 1
        threads_str = str(threads_int)
        thread_configuration = self._get_thread_configurations(request=request)
        test_on_output = self._test_on_output_events()
        current_thread = thread_configuration[threads_str]

        # Set the number of event parameters
        sequence_dict["nThreads"] = threads_int
        sequence_dict["number"] = current_thread["target_input_events"] # -n
        if test_on_output:
            sequence_dict["number_out"] = current_thread["target_output_events"] # -o

        return sequence_dict

    def _get_test_output_events(self) -> int:
        """Get the number of output events that the validation job should produce."""
        target_output_events = 100
        try:
            target_output_events = int(settings.get_value("validation_output_events"))
        except Exception:
            pass

        return target_output_events

    def _get_test_min_output_events(self) -> int:
        """
        Get the number of minimum output events that the validation job
        should produce to be considered valid.
        """
        min_output_events = 10
        try:
            min_output_events = int(settings.get_value("validation_min_output_events"))
        except Exception:
            pass

        return min_output_events

    def _test_on_output_events(self) -> bool:
        """Determine whether to run the validation based on output events."""
        test_on_output_events = True
        try:
            test_on_output_events = bool(settings.get_value("validation_test_on_output"))
        except Exception:
            pass

        return test_on_output_events

    def _get_max_number_validations(self) -> int:
        """Get the number of maximum validation test jobs to run for a request."""
        number_of_validation_tests = 4
        try:
            number_of_validation_tests = int(settings.get_value("validation_max_test_jobs"))
        except Exception:
            pass

        return number_of_validation_tests

    def _get_minimum_validation_runtime(self) -> int:
        """Get the minimum validation runtime for a validation job in seconds."""
        minimum_validation_runtime = 10 * 60 # 10 minutes
        try:
            minimum_validation_runtime = int(settings.get_value("validation_min_runtime"))
        except Exception:
            pass

        return minimum_validation_runtime

    def _get_thread_configurations(self, request) -> dict[str, dict | None]:
        """
        Get the number of output, input events, and other metadata
        for each thread configuration to consider for sending jobs.

        Args:
            request (json_layer.request.request): Request to which validation
                events will be counted.

        Returns:
            The input and output events for each thread to submit
                validation jobs.
        """
        threads_configuration = {}
        # Thread configuration to test
        threads_for_test = [1, 2, 4, 8, 16, 32]
        # Target output events expected for the validation
        output_events = self._get_test_output_events()
        # Minimum output events the validation must produce
        min_output_events = self._get_test_min_output_events()
        # Max number of seconds that validation can run for
        max_runtime = self.get_validation_max_runtime(request=request)
        # Minimum validation runtime
        min_runtime = self._get_minimum_validation_runtime()
        # Maximum number of validation jobs to run for a request
        max_number_validations = max(self._get_max_number_validations(), 1)
        # Event efficiency (a.k.a `filter_efficiency` in McM internals)
        event_efficiency = request.get_efficiency()
        # Time per event attribute
        time_event = request.get_attribute("time_event") or []

        # How many events we need to run to get the output events
        input_events = int(output_events / event_efficiency)
        # How long does this take in seconds for a single thread execution
        time_per_event = functools.reduce(operator.mul, time_event)
        if time_per_event == 0:
            time_per_event = 1.

        for number_of_threads in threads_for_test:
            target_input_events_thread = input_events
            target_output_events_thread = output_events
            truncated = False
            extended = False

            # Compute the number of input and output events
            test_runtime_for_target = target_input_events_thread * time_per_event / number_of_threads
            if test_runtime_for_target > max_runtime:
                # Validation runtime out of limits, truncate it
                target_input_events_thread = max_runtime / time_per_event * number_of_threads
                target_output_events_thread = target_input_events_thread * event_efficiency
                truncated = True
            if test_runtime_for_target < min_runtime:
                # Validation runtime will not run for long enough, extend it
                target_input_events_thread = min_runtime / time_per_event * number_of_threads
                target_output_events_thread = target_input_events_thread * event_efficiency
                extended = True

            # Check if the configuration will produce the expected number of events
            if target_output_events_thread < min_output_events:
                self.logger.info(
                    (
                        "Discarding running a validation job using %s threads for %s, "
                        "as the target output events (%s) is less than the minumum expected (%s)"
                    ),
                    number_of_threads,
                    request.get_attribute("prepid"),
                    target_output_events_thread,
                    min_output_events
                )
                continue

            if max_number_validations == 0:
                break

            max_number_validations -= 1
            threads_str = str(number_of_threads)
            threads_configuration[threads_str] = {
                "target_input_events": int(target_input_events_thread),
                "target_output_events": int(target_output_events_thread),
                "input_events": input_events,
                "output_events": output_events,
                "maximum_runtime": max_runtime,
                "minimum_runtime": min_runtime,
                "number_of_threads": number_of_threads,
                "event_efficiency": event_efficiency,
                "time_per_event": time_per_event,
                "truncated": truncated,
                "extended": extended
            }

        return threads_configuration


# Validation strategies
_ALL_VALIDATION_STRATEGIES: dict[str, ValidationStrategy] = {
    LongValidationStrategy.name(): LongValidationStrategy(),
    ShortValidationStrategy.name(): ShortValidationStrategy()
}

def get_validation_strategy(validation_name: str) -> ValidationStrategy:
    """
    Get the validation strategy for a request or chained request.

    Args:
        validation_name: Request or chained request prepid.

    Returns:
        Validation strategy to use.
    """
    strategy = _ALL_VALIDATION_STRATEGIES[LongValidationStrategy.name()]

    # Try to get the default strategy for any request via settings
    try:
        validation_strategy_default = str(settings.get_value("validation_strategy_default"))
        if validation_strategy_default in _ALL_VALIDATION_STRATEGIES:
            strategy = _ALL_VALIDATION_STRATEGIES[validation_strategy_default]
    except Exception as e:
        # The key does not exists in the database or it is malformed
        logger.warning(
            "Unable to select a default strategy via the `validation_strategy_default` setting for %s: %s",
            validation_name,
            e
        )

    # Try to get a custom-specific strategy for the request
    try:
        validation_strategy_setting = dict(settings.get_value("validation_strategy"))
        selected_stategy = validation_strategy_setting.get(validation_name)
        if selected_stategy in _ALL_VALIDATION_STRATEGIES:
            strategy = _ALL_VALIDATION_STRATEGIES[selected_stategy]
    except Exception as e:
        # The key does not exists in the database or it is malformed
        logger.warning("Unable to select a custom strategy for %s: %s", validation_name, e)

    logger.info("Validation strategy for %s: %s", validation_name, type(strategy))
    return strategy
