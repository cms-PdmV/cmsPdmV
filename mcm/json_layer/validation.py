"""Handles the different validation strategies for a request or chained request."""

from __future__ import annotations
import abc
import copy
import functools
import json
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

    @abc.abstractmethod
    def is_first_validation(self, request, threads) -> bool:
        """
        Check if the given number of threads is related to the first validation scenario.

        Args:
            request (json_layer.request.request): Request to compute validation runtime.
            threads (int): Number of threads to check.
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

    def is_first_validation(self, request, threads) -> bool:
        return threads == 1


class ShortValidationStrategy(ValidationStrategy):
    @classmethod
    def name(cls) -> str:
        return "SHORT"

    def submit_initial_validation(self, validation_control, validation_name):
        # Pick the thread configuration for all requests
        # then pick the number of threads removing duplicates
        requests = validation_control.requests_for_validation(validation_name)
        thread_config_requests = {
            request.get_attribute("prepid"): self._get_thread_configurations(request=request)
            for request in requests
        }
        threads_to_consider = []
        for config in thread_config_requests.values():
            scenarios = config["scenarios"]
            threads_for_request = {int(thread_str) for thread_str in scenarios.keys()}
            threads_to_consider.append(threads_for_request)

        threads_to_run = set.intersection(*threads_to_consider)
        if threads_to_run:
            min_thread_int = min(threads_to_run)
            validation_control.submit_item(validation_name, min_thread_int)
        else:
            min_output_events = self._get_test_min_output_events()
            message = [
                "Unable to compute validation scenarios using the short validation strategy that produce at least %s events" % (min_output_events),
                "Please find some explanations below about how the event efficiency, input events, and other metadata were computed for:",
                ""
            ]
            for request_prepid, config in thread_config_requests.items():
                message.append(f"Request: {request_prepid}")
                message.extend(config["meta_explanation"])
                message.append("")

            message.extend([
                "Most of times, this could be related to:",
                "",
                "- Big number of input events result of a low event efficiency:",
                "Check and increase the `filter_efficiency` and/or the `match_efficiency` and/or decrease their errors!",
                "",
                "- Overestimation of the `time_per_event` for the request",
                "Decrease the `time_per_event` paramater",
                "",
                "In case you need these generator parameters fixed as you provided, contact McM administrators to run this validation using another strategy"
            ])

            message_to_send = "\n".join(message)
            validation_control.validation_failed(validation_name)
            validation_control.notify_validation_failed(
                validation_name,
                message_to_send
            )

    def move_validation_to_next_stage(self, validation_control, validation_name):
        # Pick the thread configuration for all requests
        # then pick the number of threads removing duplicates
        requests = validation_control.requests_for_validation(validation_name)
        storage_item = validation_control.storage.get(validation_name)
        done_threads = {int(thread_str) for thread_str in storage_item.get("done").keys()}
        thread_config_requests = {
            request.get_attribute("prepid"): self._get_thread_configurations(request=request)
            for request in requests
        }
        threads_to_consider = []
        for config in thread_config_requests.values():
            scenarios = config["scenarios"]
            threads_for_request = {int(thread_str) for thread_str in scenarios.keys()}
            threads_to_consider.append(threads_for_request)

        threads_to_consider = set.intersection(*threads_to_consider)
        threads_to_run = threads_to_consider - done_threads
        self.logger.info("Submitting next stage for %s, threads to submit: %s", validation_name, threads_to_run)
        if threads_to_run:
            for threads_int in threads_to_run:
                validation_control.submit_item(validation_name, threads_int)

    def get_event_count_for_validation(self, request, with_explanation=False, threads=None) -> int | tuple[int, str]:
        threads_int = threads if isinstance(threads, int) else 1
        threads_str = str(threads_int)
        # Run the validation job based on output events
        test_on_output = self._test_on_output_events()
        # Validation scenarios
        validation_thread_configurations = self._get_thread_configurations(request=request)
        validation_scenarios = validation_thread_configurations["scenarios"]
        thread_config = validation_scenarios.get(threads_str)
        if not thread_config:
            self.logger.error("Unable to retrieve the validation scenario for %s threads", threads_str)
            self.logger.warning("Setting a default number of events to be able to generate a script to manually test it!")
            if with_explanation:
                not_found_message = f"# Short validation strategy: Unable to retrieve the validation scenario for {threads_str} threads"
                return 1, not_found_message
            else:
                return 1

        target_input_events = thread_config["target_input_events"]
        target_output_events = thread_config["target_output_events"]
        explanation = thread_config["explanation"]
        events_to_return = target_output_events if test_on_output else target_input_events
        if not with_explanation:
            return events_to_return

        if test_on_output:
            explanation.append("# This validation will be computed based on the target output events!")
        else:
            explanation.append("# This validation will be computed based on the target input events!")

        return events_to_return, '\n'.join(explanation)

    def tweak_cmsdriver_for_validation(self, request, sequence_dict, threads) -> dict:
        threads_int = threads if isinstance(threads, int) else 1
        threads_str = str(threads_int)
        request_prepid = request.get_attribute('prepid')

        # Run the validation job based on output events
        test_on_output = self._test_on_output_events()
        # Validation scenarios
        validation_thread_configurations = self._get_thread_configurations(request=request)
        validation_scenarios = validation_thread_configurations["scenarios"]
        thread_config = validation_scenarios.get(threads_str)
        if not thread_config:
            self.logger.error(
                "Unable to retrieve the validation scenario for %s threads for tweaking the cmsDriver for the request %s",
                threads_str,
                request_prepid
            )
            return sequence_dict

        # Input and output events
        target_input_events = thread_config["target_input_events"]
        target_output_events = thread_config["target_output_events"]

        # Set the number of event parameters
        sequence_dict["nThreads"] = threads_int
        if test_on_output:
            sequence_dict["number"] = target_input_events
            sequence_dict["number_out"] = target_output_events
        else:
            sequence_dict["number"] = target_input_events

        return sequence_dict

    def is_first_validation(self, request, threads) -> bool:
        validation_thread_configurations = self._get_thread_configurations(request=request)
        validation_scenarios = validation_thread_configurations["scenarios"]
        threads_for_request = {int(thread_str) for thread_str in validation_scenarios.keys()}
        if not threads_for_request:
            return False
        return threads == min(threads_for_request)

    def _get_test_output_events(self) -> int:
        """Get the number of output events that the validation job should produce."""
        target_output_events = 100
        try:
            target_output_events = int(settings.get_value("validation_output_events"))
        except Exception as e:
            logger.warning(
                "Unable to retrieve the target output events from `validation_output_events`: %s",
                e
            )

        return target_output_events

    def _get_test_min_output_events(self) -> int:
        """
        Get the number of minimum output events that the validation job
        should produce to be considered valid.
        """
        min_output_events = 10
        try:
            min_output_events = int(settings.get_value("validation_min_output_events"))
        except Exception as e:
            logger.warning(
                "Unable to retrieve the minimum output events to produce from `validation_min_output_events`: %s",
                e
            )

        return min_output_events

    def _test_on_output_events(self) -> bool:
        """Determine whether to run the validation based on output events."""
        test_on_output_events = True
        try:
            test_on_output_events = bool(settings.get_value("validation_test_on_output"))
        except Exception as e:
            logger.warning(
                "Unable to retrieve the `validation_test_on_output` setting: %s",
                e
            )

        return test_on_output_events

    def _get_max_number_validations(self) -> int:
        """Get the number of maximum validation test jobs to run for a request."""
        number_of_validation_tests = 4
        try:
            number_of_validation_tests = int(settings.get_value("validation_max_test_jobs"))
        except Exception as e:
            logger.warning(
                "Unable to retrieve the number of max validation jobs from `validation_max_test_jobs`: %s",
                e
            )

        return number_of_validation_tests

    def _get_minimum_validation_runtime(self) -> int:
        """Get the minimum validation runtime for a validation job in seconds."""
        minimum_validation_runtime = 10 * 60 # 10 minutes
        try:
            minimum_validation_runtime = int(settings.get_value("validation_min_runtime"))
        except Exception as e:
            logger.warning(
                "Unable to retrieve the minimum validation runtime from `validation_min_runtime`: %s",
                e
            )

        return minimum_validation_runtime

    def _get_threads_to_test(self) -> list[int]:
        """Get the number of threads for each validation scenario."""
        scenarios = [1, 2, 4, 8]
        try:
            scenarios_from_settings = settings.get_value("validation_test_scenarios")
            if isinstance(scenarios_from_settings, list):
                scenarios_to_use = [int(value) for value in scenarios_from_settings]
                scenarios = scenarios_to_use
            else:
                logger.warning(
                    "The given scenarios are not a list: Type: %s - Value: %s",
                    type(scenarios_from_settings),
                    scenarios_from_settings
                )
        except Exception as e:
            logger.warning(
                "Unable to retrieve the number of threads for the validation scenarios from `validation_test_scenarios`: %s",
                e
            )

        logger.info("Number of threads to consider for the thread configuration: %s", scenarios)
        return scenarios

    def _get_thread_configurations(self, request) -> dict[str, dict]:
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
        threads_for_test = self._get_threads_to_test()
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
        # Discarded scenarios
        explantation_discarded_scenarios = []
        # Explanation
        explanation = [
            "# Maximum validation runtime: %ds" % (max_runtime),
            "# Minimum validation runtime: %ds" % (min_runtime),
            "# Output events to run for the validation job (from application's setting): %d" % (output_events)
        ]

        # Event efficiency
        eff = request.get_efficiency()
        eff_err = request.get_efficiency_error(relative=False)
        explanation.append("# Event efficiency: Computed using the request efficiency and its error.")

        event_efficiency = eff - (2 * eff_err)
        event_efficiency_explanation = "# Event efficiency: `efficiency - (2 * efficiency_error)`: `%.3g - (2 * %.3g)` = %.3g" % (eff, eff_err, event_efficiency)
        if event_efficiency < 0:
            event_efficiency = eff - eff_err
            event_efficiency_explanation = "# Event efficiency: `efficiency - efficiency_error`: `%.3g - %.3g` = %.3g" % (eff, eff_err, event_efficiency)
        if event_efficiency < 0:
            event_efficiency = eff / 2.
            event_efficiency_explanation = "# Event efficiency: `efficiency / 2.`: `%.3g / 2.` = %.3g" % (eff, event_efficiency)
        if event_efficiency == 0:
            event_efficiency = 1.
            event_efficiency_explanation = "# Event efficiency: Set to 1 because efficiency is zero"

        explanation.append(event_efficiency_explanation)

        # Time per event attribute
        time_event = request.get_attribute("time_event") or []
        # How many events we need to run to get the output events
        input_events = int(output_events / event_efficiency)
        explanation.append(
            "# Input events: `int(output_events / event_efficiency)`: `int(%d / %.3g)` = %d" % (
                output_events, event_efficiency, input_events
            )
        )

        # How long does this take in seconds for a single thread execution
        explanation.append("# Time per event (s): Computed adding all the time_per_event values on every sequence")
        time_per_event = functools.reduce(operator.add, time_event)
        time_per_event_explanation = "# Time per event (s): %.3g" % (time_per_event)
        if time_per_event == 0:
            time_per_event = 1.
            time_per_event_explanation = "# Time per event (s): Set to 1s because its sum its zero"

        explanation.append(time_per_event_explanation)

        for number_of_threads in threads_for_test:
            explanation_case = []
            target_input_events_thread = input_events
            target_output_events_thread = output_events

            # Compute the number of input and output events
            test_runtime_for_target = target_input_events_thread * time_per_event / number_of_threads
            if test_runtime_for_target > max_runtime:
                # Validation runtime out of limits, truncate it
                target_input_events_thread = max_runtime / time_per_event * number_of_threads
                target_output_events_thread = target_input_events_thread * event_efficiency
                explanation_case.extend([
                    "# Validation runtime out of limits, truncating the time",
                    "# Target input events changed to: `maximum_runtime / time_per_event * number_of_threads`: `%.3g / %.3g * %d` = %.3g" % (
                        max_runtime, time_per_event, number_of_threads, target_input_events_thread
                    ),
                    "# Target output events change to: `target_input_events * event_efficiency`: `%.3g * %.3g` = %.3g" % (
                        target_input_events_thread, event_efficiency, target_output_events_thread
                    )
                ])

            if test_runtime_for_target < min_runtime:
                # Validation runtime will not run for long enough, extend it
                target_input_events_thread = min_runtime / time_per_event * number_of_threads
                target_output_events_thread = target_input_events_thread * event_efficiency
                explanation_case.extend([
                    "# Validation runtime will not run for long enough than expected, extending the time",
                    "# Target input events changed to: `minimum_runtime / time_per_event * number_of_threads`: `%d / %.3g * %d` = %.3g" % (
                        min_runtime, time_per_event, number_of_threads, target_input_events_thread
                    ),
                    "# Target output events changed to: `target_input_events * event_efficiency`: `%.3g * %.3g` = %.3g" % (
                        target_input_events_thread, event_efficiency, target_output_events_thread
                    )
                ])

            # Check if the configuration will produce the expected number of events
            if target_output_events_thread < min_output_events:
                discarded_message = (
                    f"# Discarding running a validation job using {number_of_threads} threads for {request.get_attribute('prepid')}, "
                    f"as the target output events ({target_output_events_thread}) is less than the minimum expected ({min_output_events})"
                )
                explantation_discarded_scenarios.append(discarded_message)
                self.logger.info(discarded_message)
                continue

            if max_number_validations == 0:
                break

            # Explain if there were changes on the initial values
            target_output_events = int(target_output_events_thread)
            target_input_events = int(target_input_events_thread)
            events_modified = (
                (input_events != target_input_events_thread)
                or (output_events != target_output_events_thread)
            )
            final_explanation = copy.deepcopy(explanation)
            if not events_modified:
                final_explanation.extend([
                    "# Target input events: %d" % (target_input_events),
                    "# Target output events: %d" % (target_output_events),
                ])
            else:
                final_explanation.extend([
                    "# Initial target input events: %d" % (input_events),
                    "# Initial target output events: %d" % (output_events)
                ])
                final_explanation.extend(explanation_case)
                final_explanation.extend([
                    "# Final target input events: %d" % (target_input_events),
                    "# Final target output events: %d" % (target_output_events)
                ])

            max_number_validations -= 1
            threads_str = str(number_of_threads)
            threads_configuration[threads_str] = {
                "target_input_events": target_input_events,
                "target_output_events": target_output_events,
                "explanation": final_explanation
            }

        meta_explanation = explanation + explantation_discarded_scenarios
        result = {
            "meta_explanation": meta_explanation,
            "scenarios": threads_configuration,
        }
        self.logger.info(
            "Thread configuration for request %s: %s",
            request.get_attribute("prepid"), json.dumps(result, indent=2, sort_keys=True)
        )
        return result


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
