<template>
  <v-container>
    <h1 class="page-title"><span class="font-weight-light">Editing campaign</span> {{prepid}}</h1>
    <v-card raised class="page-card pa-2">
      <table class="edit-table" v-if="object.prepid">
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
                    {{object.sequences[name][index].datatier.join(',')}}: <input type="checkbox" v-model="values[index]" :disabled="!editable.keep_output"/>
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
          <td><textarea v-model="object.sequences" :disabled="!editable.sequences"></textarea></td>
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
    <v-overlay :value="loading"><v-progress-circular indeterminate size="32"></v-progress-circular></v-overlay>
    <footer style="text-align: center">
      <v-btn small class="ml-1 mr-1" color="success" title="Save and return" @click="save(true)">Save</v-btn>
      <v-btn small class="ml-1 mr-1" color="success" title="Save and stay in this page" @click="save(false)">Save & stay</v-btn>
      <v-btn small class="ml-1 mr-1" color="primary" title="Cancel editing" @click="cancelEdit()">Cancel</v-btn>
      <v-btn small class="ml-1 mr-1" color="error" title="Delete this object" @click="promptDelete(object)">Delete</v-btn>
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
  },
  mixins: [roleMixin, utilsMixin, editPageMixin],
  data() {
    return {
      databaseName: 'campaigns',
      showRaw: false,
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
  },
};
</script>

<style scoped>

footer button {
  margin-top: 7px;
}

</style>