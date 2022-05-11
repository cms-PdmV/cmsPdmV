<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Requests</h1>
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
        <router-link :to="databaseName + '?cmssw_release=' + item.cmssw_release" custom title="Requests with this CMSSW release" class="bold-hover">{{item.cmssw_release}}</router-link>
      </template>
      <template v-slot:[`item.generators`]="{ item }">
        <ul>
          <li v-for="generator in item.generators" :key="generator">{{generator}}</li>
        </ul>
      </template>
      <template v-slot:[`item.keep_output`]="{ item }">
        <ol>
          <li v-for="(value, index) in item.keep_output" :key="index">{{value}}</li>
        </ol>
      </template>
      <template v-slot:[`item.sequences`]="{ item }">
        {{item.sequences}}
      </template>
      <template v-slot:[`item.pileup_dataset_name`]="{ item }">
        <a :href="dasLink(item.pileup_dataset_name)" title="Open in DAS" target="_blank" class="bold-hover">{{item.pileup_dataset_name}}</a>
      </template>

    </v-data-table>
    <delete-prompt ref="delete-prompt"></delete-prompt>
    <error-dialog ref="error-dialog"></error-dialog>
    <footer>
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
  name: 'requests',
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
      databaseName: 'requests',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: true, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: true },
        { dbName: 'approval', visible: true },
        { dbName: 'status', visible: true },
        { dbName: 'history', sortable: true },
        { dbName: 'keep_output', visible: true },
        { dbName: 'memory', visible: true },
        { dbName: 'notes', visible: true },
        { dbName: 'sequences', visible: true },
        { dbName: 'cmssw_release' },
        { dbName: 'completed_events' },
        { dbName: 'config_id' },
        { dbName: 'dataset_name' },
        { dbName: 'energy' },
        { dbName: 'events_per_lumi' },
        { dbName: 'extension' },
        { dbName: 'flown_with' },
        { dbName: 'fragment' },
        { dbName: 'fragment_name' },
        { dbName: 'fragment_tag' },
        { dbName: 'generator_parameters' },
        { dbName: 'generators' },
        { dbName: 'input_dataset' },
        { dbName: 'interested_pwg' },
        { dbName: 'mcdb_id' },
        { dbName: 'member_of_campaign' },
        { dbName: 'member_of_chain' },
        { dbName: 'name_of_fragment' },
        { dbName: 'output_dataset' },
        { dbName: 'pileup_dataset_name' },
        { dbName: 'pilot' },
        { dbName: 'priority' },
        { dbName: 'process_string' },
        { dbName: 'pwg' },
        { dbName: 'reqmgr_name' },
        { dbName: 'size_event' },
        { dbName: 'tags' },
        { dbName: 'time_event' },
        { dbName: 'total_events' },
        { dbName: 'type' },
        { dbName: 'validation' },
        { dbName: 'version' }
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
    promptDelete: function(item) {
      this.$refs['delete-prompt'].open(this.databaseName, item, (response) => {
        if (response.results) {
          this.fetchObjects();
        } else if (response.message) {
          this.showError(response.message);
        }
      }, (error) => {
        this.showError(error);
      });
    },
    showError: function(errorMessage) {
      this.$refs['error-dialog'].open(errorMessage);
    },
  },
};
</script>
