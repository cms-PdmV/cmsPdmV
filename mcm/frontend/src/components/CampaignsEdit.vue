<template>
  <v-container>
    <h1 class="page-title">
      <template v-if="prepid">
        <span class="font-weight-light">Editing campaign</span> {{prepid}}
      </template>
      <template v-else>
        <span class="font-weight-light">Creating</span> new <span class="font-weight-light">campaign</span>
      </template>
    </h1>
    <v-card raised class="page-card pa-2">
      <table class="edit-table" v-if="Object.keys(object).length">
        <tr>
          <td>Prepid</td>
          <td><input type="text" v-model="object.prepid" :disabled="!editable.prepid"/></td>
        </tr>
        <tr>
          <td>CMSSW release</td>
          <td><autocompleter v-model="object.cmssw_release" :getSuggestions="getCmsswSuggestions" :disabled="!editable.cmssw_release"></autocompleter></td>
        </tr>
        <tr>
          <td>Energy</td>
          <td><input type="number" v-model="object.energy" :disabled="!editable.energy"/></td>
        </tr>
        <tr>
          <td>Events per lumi</td>
          <td>
            <table class="edit-table">
              <tr>
                <td>Singlecore:</td>
                <td><input type="number" v-model="object.events_per_lumi.singlecore" :disabled="!editable.events_per_lumi"/></td>
              </tr>
              <tr>
                <td>Multicore:</td>
                <td><input type="number" v-model="object.events_per_lumi.multicore" :disabled="!editable.events_per_lumi"/></td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td>Generators</td>
          <td>
            <editable-list v-model="object.generators"
                           :getSuggestions="getGeneratorSuggestions"
                           :disabled="!editable.generators"></editable-list>
          </td>
        </tr>
        <tr>
          <td>Input dataset</td>
          <td><input type="text" v-model="object.input_dataset" :disabled="!editable.input_dataset"/></td>
        </tr>
        <tr>
          <td>Keep output</td>
          <td>
            <ul>
              <li v-for="(values, name) in object.keep_output" :key="name"><b>{{name}}</b>:
                <ol>
                  <li v-for="(value, index) in values" :key="index">
                    {{sequenceName(object.sequences[name][index])}}: <input type="checkbox" v-model="values[index]" :disabled="!editable.keep_output"/>
                  </li>
                </ol>
              </li>
            </ul>
          </td>
        </tr>
        <tr>
          <td>Memory</td>
          <td><input type="number" v-model="object.memory" :disabled="!editable.memory"/></td>
        </tr>
        <tr>
          <td>Notes</td>
          <td><textarea v-model="object.notes" :disabled="!editable.notes"></textarea></td>
        </tr>
        <tr>
          <td>Pileup dataset name</td>
          <td><input type="text" v-model="object.pileup_dataset_name" :disabled="!editable.pileup_dataset_name"/></td>
        </tr>
        <tr>
          <td>Root</td>
          <td>
            <select v-model="object.root" :disabled="!editable.root">
              <option value="0">Yes</option>
              <option value="1">No</option>
              <option value="-1">Possible</option>
            </select>
          </td>
        </tr>
        <tr>
          <td>Sequences</td>
          <td>
            <ul>
              <li v-for="(sequences, name) in object.sequences" :key="name">
                <b>{{name}}</b>:
                <small class="small-button" style="color: var(--v-anchor-base);" title="Rename sequence group" @click="renameSequenceGroup(name)">Rename</small>
                <small class="small-button" style="color: red" title="Delete sequence group" @click="deleteSequenceGroup(name)">Delete</small>
                <ol>
                  <li v-for="(sequence, index) in sequences" :key="index">
                    {{sequenceName(sequence)}}:
                    <small class="small-button" style="color: var(--v-anchor-base);" title="Edit sequence" @click="editSequence(sequences, index)">Edit</small>
                    <small class="small-button" style="color: red" title="Delete sequence" @click="deleteSequence(name, sequences, index)">Delete</small>
                    <br>
                    <div class="sequence-field">{{makeDriver(sequence)}}</div>
                  </li>
                </ol>
                <small class="small-button" style="color: green" title="Add new sequence" @click="addSequence(name, sequences)">Add sequence</small>
              </li>
            </ul>
            <small class="small-button" style="color: green" title="Add new sequence group" @click="addSequenceGroup()">Add group</small>
          </td>
        </tr>
        <tr>
          <td>Type</td>
          <td>
            <select v-model="object.type" :disabled="!editable.type">
              <option>LHE</option>
              <option>Prod</option>
              <option>MCReproc</option>
            </select>
          </td>
        </tr>
        <tr>
          <td>WWW</td>
          <td><input type="text" v-model="object.www" :disabled="!editable.www"/></td>
        </tr>
      </table>
      <pre v-if="showRaw" style="font-size: 0.6em">{{JSON.stringify(object, null, 2)}}</pre>
      <small @click="showRaw = !showRaw" class="bold-hover" style="cursor: pointer">{{showRaw ? 'Hide raw JSON' : 'Show raw JSON'}}</small>
    </v-card>
    <delete-prompt ref="delete-prompt"></delete-prompt>
    <error-dialog ref="error-dialog"></error-dialog>
    <sequence-edit ref="sequence-edit"></sequence-edit>
    <rename-prompt ref="rename-prompt"></rename-prompt>
    <v-overlay :value="loading"><v-progress-circular indeterminate size="32"></v-progress-circular></v-overlay>
    <footer style="text-align: center">
      <v-btn small class="ml-1 mr-1" color="success" title="Save and return" @click="save(true)">Save</v-btn>
      <v-btn small class="ml-1 mr-1" color="success" title="Save and stay in this page" @click="save(false)">Save & stay</v-btn>
      <v-btn small class="ml-1 mr-1" color="primary" title="Cancel editing" @click="cancelEdit()">Cancel</v-btn>
      <v-btn small class="ml-1 mr-1" v-if="object._rev" color="error" title="Delete this object" @click="promptDelete(object)">Delete</v-btn>
    </footer>
  </v-container>
</template>

<script>
import axios from 'axios';
import DeletePrompt from './DeletePrompt.vue';
import ErrorDialog from './ErrorDialog.vue';
import HistoryCell from './HistoryCell'
import EditableList from './EditableList.vue';
import Autocompleter from './Autocompleter.vue';
import SequenceEdit from './SequenceEdit.vue';
import RenamePrompt from './RenamePrompt.vue';
import { roleMixin } from '../mixins/UserRoleMixin.js';
import { utilsMixin } from '../mixins/UtilsMixin.js';
import { editPageMixin } from '../mixins/EditPageMixin.js';

export default {
  name: 'campaigns-edit',
  components: {
    DeletePrompt,
    ErrorDialog,
    HistoryCell,
    EditableList,
    Autocompleter,
    SequenceEdit,
    RenamePrompt,
  },
  mixins: [roleMixin, utilsMixin, editPageMixin],
  data() {
    return {
      databaseName: 'campaigns',
      showRaw: false,
      defaultSchema: undefined,
    };
  },
  methods: {
    getGeneratorSuggestions: function(query, callback) {
      return axios.get(`restapi/${this.databaseName}/unique_values?attribute=generators&value=${query}`)
        .then(response => callback(response.data.results));
    },
    getCmsswSuggestions: function(query, callback) {
      return axios.get(`restapi/${this.databaseName}/unique_values?attribute=cmssw_release&value=${query}`)
        .then(response => callback(response.data.results));
    },
    prepareForEdit: function(object) {
      for (let name in object.sequences) {
        let sequences = object.sequences[name];
        for (let sequence of sequences) {
          sequence.datatier = sequence.datatier.join(',');
          sequence.eventcontent = sequence.eventcontent.join(',');
          sequence.step = sequence.step.join(',');
        }
      }
    },
    prepareForSave: function(object) {
      for (let name in object.sequences) {
        let sequences = object.sequences[name];
        for (let sequence of sequences) {
          sequence.datatier = sequence.datatier.split(',');
          sequence.eventcontent = sequence.eventcontent.split(',');
          sequence.step = sequence.step.split(',');
          sequence.nThreads = parseInt(sequence.nThreads);
          sequence.nStreams = parseInt(sequence.nStreams);
          sequence.index = parseInt(sequence.index);
        }
      }
    },
    editSequence: function(sequences, index) {
      let sequence = JSON.parse(JSON.stringify(sequences[index]));
      this.$refs['sequence-edit'].open(sequence, (sequence) => {
        Object.assign(sequences[index], sequence);
      });
    },
    deleteSequence: function(name, sequences, index) {
      sequences.splice(index, 1);
      this.object.keep_output[name].splice(index, 1);
    },
    addSequence: function(name, sequences) {
      if (this.defaultSchema) {
        let sequence = JSON.parse(JSON.stringify(this.defaultSchema));
        sequences.push(sequence);
        this.object.keep_output[name].push(true);
      } else {
        axios.get(`restapi/campaigns/get_default_sequence`).then(response => {
          this.defaultSchema = JSON.parse(JSON.stringify(response.data.results));
          this.addSequence(name, sequences);
        });
      }
    },
    renameSequenceGroup: function(name) {
      this.$refs['rename-prompt'].open(name, (newName) => {
        if (newName in this.object.sequences) {
          this.showError(`Sequence group with name "${newName}" already exists`);
        } else {
          this.$set(this.object.sequences, newName, this.object.sequences[name]);
          this.deleteSequenceGroup(name);
        }
      });
    },
    deleteSequenceGroup: function(name) {
      this.$delete(this.object.keep_output, name);
      this.$delete(this.object.sequences, name);
    },
    addSequenceGroup: function() {
      let name = 'default';
      let i = 0;
      while (name in this.object.sequences) {
        i++;
        name = `default-${i}`;
      }
      this.$set(this.object.sequences, name, []);
      this.$set(this.object.keep_output, name, []);
    },
  },
};
</script>

<style scoped>

.small-button {
  cursor: pointer;
  margin-left: 2px;
  margin-right: 2px;
}

</style>
