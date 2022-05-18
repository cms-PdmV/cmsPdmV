<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Campaigns</h1>
        <ColumnSelector :columns="columns" v-on:updateHeaders="updateTableHeaders" />
      </div>
    </div>

    <v-data-table
      :headers="headers"
      :items="items"
      :loading="loading"
      :options.sync="optionsSync"
      :server-items-length="totalItems"
      hide-default-footer
      class="elevation-1"
      dense
      :items-per-page="itemsPerPage"
    >
      <template v-slot:[`item._actions`]="{ item }">
        <div class="actions">
          <a :href="databaseName + '/edit?prepid=' + item.prepid" v-if="role('production_manager')" title="Edit">Edit</a>
          <a @click="promptDelete(item)" v-if="role('production_expert')" title="Delete">Delete</a>
          <a :href="'restapi/' + databaseName + '/get/' + item.prepid" v-if="role('administrator')" title="Raw object JSON">Raw</a>
          <a @click="toggleStatus(item)" v-if="role('production_expert')" title="Toggle campaign status">Toggle</a>
          <router-link :to="'flows?uses=' + item.prepid" custom title="Flows that use campaign">Flows</router-link>
          <router-link :to="'chained_campaigns?contains=' + item.prepid" custom title="Chained campaigns that use campaign">Chained&nbsp;campaigns</router-link>
          <router-link :to="'requests?member_of_campaign=' + item.prepid" custom title="Requests in campaign">Requests</router-link>
        </div>
      </template>
      <template v-slot:[`item.prepid`]="{ item }">
        <router-link :to="databaseName + '?prepid=' + item.prepid" custom :title="'Show only ' + item.prepid" class="bold-hover">{{item.prepid}}</router-link>
      </template>
      <template v-slot:[`item.history`]="{ item }">
        <HistoryCell :data="item.history"/>
      </template>
      <template v-slot:[`item.notes`]="{ item }">
        <pre v-if="item.notes.length" v-html="sanitize(item.notes)" class="notes" v-linkified></pre>
      </template>
      <template v-slot:[`item.cmssw_release`]="{ item }">
        <router-link :to="databaseName + '?cmssw_release=' + item.cmssw_release" custom title="Campaigns with this CMSSW release" class="bold-hover">{{item.cmssw_release}}</router-link>
      </template>
      <template v-slot:[`item.type`]="{ item }">
        <router-link :to="databaseName + '?type=' + item.type" custom title="Campaigns with this type" class="bold-hover">{{item.type}}</router-link>
      </template>
      <template v-slot:[`item.next`]="{ item }">
        <ul>
          <li v-for="nextCampaign in item.next" :key="nextCampaign">
            <router-link :to="databaseName + '?prepid=' + nextCampaign" custom :title="'Show only ' + nextCampaign" class="bold-hover">{{nextCampaign}}</router-link>
          </li>
        </ul>
      </template>
      <template v-slot:[`item.generators`]="{ item }">
        <ul>
          <li v-for="generator in item.generators" :key="generator">{{generator}}</li>
        </ul>
      </template>
      <template v-slot:[`item.events_per_lumi`]="{ item }">
          <small>Singlecore:</small>&nbsp;{{item.events_per_lumi.singlecore}}
          <br>
          <small>Multicore:</small>&nbsp;{{item.events_per_lumi.multicore}}
      </template>
      <template v-slot:[`item.keep_output`]="{ item }">
        <ul>
          <li v-for="(values, name) in item.keep_output" :key="name"><b>{{name}}</b>:
            <ol>
              <li v-for="(value, index) in values" :key="index">{{value}}</li>
            </ol>
          </li>
        </ul>
      </template>
      <template v-slot:[`item.sequences`]="{ item }">
        <ul>
          <li v-for="(sequences, sequenceName) in item.sequences" :key="sequenceName">
            {{sequenceName}}:
            <ul>
              <li v-for="(sequence, index) in sequences" :key="index">
                {{sequence.datatier.join(',')}}:
                <div class="sequence-field">{{makeDriver(sequence)}}</div>
              </li>
            </ul>
          </li>
        </ul>
      </template>
      <template v-slot:[`item.pileup_dataset_name`]="{ item }">
        <a :href="dasLink(item.pileup_dataset_name)" title="Open in DAS" target="_blank" class="bold-hover">{{item.pileup_dataset_name}}</a>
      </template>
      <template v-slot:[`item.status`]="{ item }">
        <router-link :to="databaseName + '?status=' + item.status" custom :title="'Show only ' + item.status" class="bold-hover">{{item.status}}</router-link>
      </template>
    </v-data-table>
    <delete-prompt ref="delete-prompt"></delete-prompt>
    <error-dialog ref="error-dialog"></error-dialog>
    <footer>
      <v-btn small class="ml-1 mr-1" color="success" title="Create a new campaign" @click="createNew()">Create new campaign</v-btn>
      <Paginator :totalRows="totalItems" v-on:update="onPaginatorUpdate"/>
    </footer>
  </div>
</template>

<script>
import axios from 'axios';
import ColumnSelector from './ColumnSelector';
import DeletePrompt from './DeletePrompt.vue';
import ErrorDialog from './ErrorDialog.vue';
import Paginator from './Paginator.vue';
import HistoryCell from './HistoryCell'
import { roleMixin } from '../mixins/UserRoleMixin.js';
import { utilsMixin } from '../mixins/UtilsMixin.js';
import { dataTableMixin } from '../mixins/DataTableMixin.js';
import { navigationMixin } from '../mixins/NavigationMixin.js';

export default {
  name: 'campaigns',
  components: {
    ColumnSelector,
    DeletePrompt,
    ErrorDialog,
    Paginator,
    HistoryCell,
  },
  mixins: [roleMixin, utilsMixin, dataTableMixin, navigationMixin],
  data() {
    return {
      databaseName: 'campaigns',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: true, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: true },
        { dbName: 'cmssw_release', displayName: 'CMSSW release', visible: true, sortable: true },
        { dbName: 'energy', sortable: true },
        { dbName: 'events_per_lumi', visible: true },
        { dbName: 'generators', visible: true },
        { dbName: 'history', sortable: true },
        { dbName: 'input_dataset' },
        { dbName: 'keep_output', visible: true },
        { dbName: 'memory', visible: true },
        { dbName: 'next', visible: true },
        { dbName: 'notes', visible: true },
        { dbName: 'pileup_dataset_name', displayName: 'Pileup dataset' },
        { dbName: 'root', visible: true },
        { dbName: 'sequences' },
        { dbName: 'status', visible: true, sortable: true },
        { dbName: 'type', visible: true },
        { dbName: 'www', displayName: 'WWW' },
      ],
      items: [],
      totalItems: 0,
      itemsPerPage: 1,
      loading: false,
    };
  },
  methods: {
    fetchObjects: function() {
      this.loading = true;
      this.fetchItems(this.databaseName)
        .then(
          (response) => {
            const items = response.data.results;
            for (const item of items) {
              item._actions = '';
            }
            this.checkAttributes(this.columns, items);
            this.items = items;
            this.totalItems = response.data.total_rows;
            this.loading = false;
          },
          (error) => {
            this.showError(error);
            this.loading = false;
          },
        )
        .catch((error) => {
          this.showError(error);
          this.loading = false;
        });
    },
    onPaginatorUpdate: function(page, itemsPerPage) {
      this.itemsPerPage = itemsPerPage;
      this.fetchObjects();
    },
    toggleStatus: function(item) {
      axios
        .post('restapi/' + this.databaseName + '/status', {'prepid': item.prepid})
        .then(
          (response) => {
            if (response.data.results) {
              this.fetchObjects();
            } else if (response.data.message) {
              this.showError(response.data.message);
            }
          },
          (error) => {
            this.showError(error);
          },
        )
        .catch((error) => {
          this.onError(error);
        });
    },
  },
};
</script>
