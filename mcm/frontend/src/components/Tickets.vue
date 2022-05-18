<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">MccM tickets</h1>
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
  name: 'mccms',
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
      databaseName: 'mccms',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: 1, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: 1 },
        { dbName: 'history', sortable: true },
        { dbName: 'notes', visible: 1 },
        { dbName: 'block' },
        { dbName: 'chains', visible: 1 },
        { dbName: 'generated_chains' },
        { dbName: 'meeting', visible: 1 },
        { dbName: 'pwg' },
        { dbName: 'repetitions' },
        { dbName: 'requests', visible: 1 },
        { dbName: 'status', visible: 1 },
        { dbName: 'tags' },
        { dbName: 'total_events' },
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
  },
};
</script>
