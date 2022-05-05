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
      hide-default-footer
      class="elevation-1"
      dense
      :items-per-page="items.length"
    >
      <template v-slot:[`item._actions`]="{ item }">
        <div class="actions">
          <a :href="databaseName + '/edit?prepid=' + item.prepid" v-if="role('production_manager')" title="Edit">Edit</a>
          <a @click="promptDelete(item)" v-if="role('production_expert')" title="Delete">Delete</a>
          <a @click="toggleStatus(item)" v-if="role('production_expert')" title="Toggle campaign status">Toggle</a>
          <router-link :to="'flows?uses=' + item.prepid" custom title="Flows that use campaign">Flows</router-link>
          <router-link :to="'chained_campaigns?contains=' + item.prepid" custom title="Chained campaigns that use campaign">Chained&nbsp;campaigns</router-link>
          <router-link :to="'requests?member_of_campaign=' + item.prepid" custom title="Requests in campaign">Requests</router-link>
        </div>
      </template>
      <template v-slot:[`item.prepid`]="{ item }">
        <a :href="databaseName + '?prepid=' + item.prepid" title="Show only this item">{{ item.prepid }}</a>
      </template>
      <template v-slot:[`item.notes`]="{ item }">
        <pre v-if="item.notes.length" v-html="sanitize(item.notes)" class="notes" v-linkified></pre>
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
import { roleMixin } from '../mixins/UserRoleMixin.js';
import { utilsMixin } from '../mixins/UtilsMixin.js';

export default {
  name: 'campaigns',
  components: {
    ColumnSelector,
    DeletePrompt,
    ErrorDialog,
    Paginator,
  },
  mixins: [roleMixin, utilsMixin],
  data() {
    return {
      databaseName: 'campaigns',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: true, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: true },
        { dbName: 'cmssw_release', displayName: 'CMSSW release', visible: true },
        { dbName: 'energy' },
        { dbName: 'events_per_lumi', visible: true },
        { dbName: 'generators', visible: true },
        { dbName: 'history' },
        { dbName: 'input_dataset' },
        { dbName: 'keep_output', visible: true },
        { dbName: 'memory', visible: true },
        { dbName: 'next', visible: true },
        { dbName: 'notes', visible: true },
        { dbName: 'pileup_dataset_name', displayName: 'Pileup dataset' },
        { dbName: 'root', visible: true },
        { dbName: 'sequences', visible: true },
        { dbName: 'status', visible: true },
        { dbName: 'type', visible: true },
        { dbName: 'www', displayName: 'WWW' },
      ],
      headers: [],
      items: [],
      totalItems: 0,
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
    updateTableHeaders: function(headers) {
      this.headers = headers;
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
