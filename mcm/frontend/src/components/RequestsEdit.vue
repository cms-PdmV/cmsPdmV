<template>
  <v-container>
    <h1 class="page-title">
      <template v-if="prepid">
        <span class="font-weight-light">Editing request</span> {{prepid}}
      </template>
      <template v-else>
        <span class="font-weight-light">Creating</span> new <span class="font-weight-light">request</span>
      </template>
    </h1>
    <v-card raised class="page-card pa-2">
      <table class="edit-table" v-if="Object.keys(object).length">
        <tr>
          <td>Notes</td>
          <td><textarea v-model="object.notes" :disabled="!editable.notes"></textarea></td>
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
import { roleMixin } from '../mixins/UserRoleMixin.js';
import { utilsMixin } from '../mixins/UtilsMixin.js';
import { editPageMixin } from '../mixins/EditPageMixin.js';

export default {
  name: 'requests-edit',
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
      databaseName: 'requests',
      showRaw: false,
    };
  },
  methods: {

  },
};
</script>
