<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Chained campaigns</h1>
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
          <a @click="toggleEnabled(item)" v-if="role('production_expert')" title="Toggle enabled">Toggle</a>
          <router-link :to="'chained_requests?member_of_campaign=' + item.prepid" custom title="Chained requests that are members">Chained&nbsp;requests</router-link>
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
      <template v-slot:[`item.campaigns`]="{ item }">
        <div v-for="pair in item.campaigns" :key="pair[1]" style="white-space: nowrap;">
          <template v-if="pair[1]">
            <router-link :to="'flows?prepid=' + pair[1]" custom :title="'Show ' + pair[1]" class="bold-hover">{{pair[1]}}</router-link>
            &#8658;
          </template>
          <router-link :to="'campaigns?prepid=' + pair[0]" custom :title="'Show ' + pair[0]" class="bold-hover">{{pair[0]}}</router-link>
        </div>
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
  name: 'chained_campaigns',
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
      databaseName: 'chained_campaigns',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: 1, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: 1 },
        { dbName: 'enabled', visible: 1 },
        { dbName: 'notes', visible: 1 },
        { dbName: 'history', sortable: true },
        { dbName: 'campaigns', visible: 1 },
        { dbName: 'check_cmssw_version'},
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
    toggleEnabled: function(item) {
      axios
        .post('restapi/' + this.databaseName + '/toggle_enabled', {'prepid': item.prepid})
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
