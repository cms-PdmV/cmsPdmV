<template>
  <v-container>
    <h1 class="page-title">
      <template v-if="prepid">
        <span class="font-weight-light">Editing chained campaign</span> {{prepid}}
      </template>
      <template v-else>
        <span class="font-weight-light">Creating</span> new <span class="font-weight-light">chained campaign</span>
      </template>
    </h1>
    <v-card raised class="page-card pa-2">
      <table class="edit-table" v-if="Object.keys(object).length">
        <tr>
          <td>Campaigns</td>
          <td>
            <ol v-if="editable.campaigns">
              <li v-for="(pair, index) in object.campaigns" :key="index" class="mt-1 mb-1">
                <select v-model="pair[1]" v-if="index > 0" :disabled="!editable.campaigns" @change="selectFlow(index, $event.target.value)">
                  <option value="" disabled hidden selected>Select flow after {{object.campaigns[index-1][0]}}</option>
                  <option v-for="suggestion in suggestions[index][1]" :key="'flow_' + index + '_' + suggestion.prepid">{{suggestion.prepid}}</option>
                </select>
                <select v-model="pair[0]" v-if="index == 0" :disabled="!editable.campaigns" @change="selectCampaign(index, $event.target.value)">
                  <option value="" disabled hidden selected>Select root campaign</option>
                  <option v-for="suggestion in suggestions[index][0]" :key="'campaign_' + index + '_' + suggestion">{{suggestion}}</option>
                </select>
                <template v-if="index > 0">
                  &#8658; {{pair[0]}}
                </template>
              </li>
            </ol>
            <ol v-else>
              <li v-for="(pair, index) in object.campaigns" :key="index" class="mt-1 mb-1">
                <template v-if="index == 0">
                  {{pair[0]}}
                </template>
                <template v-else>
                  {{pair[1]}} &#8658; {{pair[0]}}
                </template>
              </li>
            </ol>
          </td>
        </tr>
        <tr>
          <td>Check CMSSW version</td>
          <td><input type="checkbox" v-model="object.check_cmssw_version" :disabled="!editable.check_cmssw_version"/></td>
        </tr>
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
import { roleMixin } from '../mixins/UserRoleMixin.js';
import { utilsMixin } from '../mixins/UtilsMixin.js';
import { editPageMixin } from '../mixins/EditPageMixin.js';

export default {
  name: 'chained-campaigns-edit',
  components: {
    DeletePrompt,
    ErrorDialog,
    HistoryCell,
  },
  mixins: [roleMixin, utilsMixin, editPageMixin],
  data() {
    return {
      databaseName: 'chained_campaigns',
      showRaw: false,
      suggestions: [],
    };
  },
  methods: {
    prepareForEdit(object) {
      if (object.campaigns.length == 0) {
        object.campaigns.push(['', '']);
        this.suggestions.push([[], []]);
        this.fetchCampaigns();
      }
    },
    prepareForSave(object) {
      object.campaigns = object.campaigns.filter(pair => pair[0] && pair[0].length);
    },
    fetchCampaigns() {
      axios.get("search?db_name=campaigns&page=-1&status=started").then(response => {
        let campaigns = response.data.results.filter(c => c.root != 1).map(c => c.prepid).sort();
        this.$set(this.suggestions, 0, [campaigns, []]);
      });
    },
    selectCampaign(index, value) {
      this.object.campaigns = this.object.campaigns.slice(0, index + 1);
      this.suggestions = this.suggestions.slice(0, index + 1);
      this.object.campaigns[index][0] = value;
      axios.get(`search?db_name=flows&page=-1&allowed_campaigns=` + value).then(response => {
        let nextFlows = response.data.results.map(flow => { const x = { 'prepid': flow.prepid, 'next': flow.next_campaign }; return x });
        if (nextFlows.length > 0) {
          nextFlows.unshift({ 'prepid': '', 'next': '' });
          this.suggestions.push([[], nextFlows]);
          this.object.campaigns.push(['', '']);
        }
      });
    },
    selectFlow(index, value) {
      for (let suggestion of this.suggestions[index][1]) {
        if (suggestion.prepid == value) {
          this.suggestions[index][0] = [suggestion.next];
          this.selectCampaign(index, suggestion.next);
          break;
        }
      }
    }
  },
};
</script>

<style scoped>

select {
  width: 60%;
}

</style>
