<template>
  <div>
    <div>
      <div>
        <h1 class="page-title">Flows</h1>
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
          <a @click="toggleType(item)" v-if="role('production_expert')" title="Toggle flow type">Toggle</a>
          <router-link :to="'chained_campaigns?contains=' + item.prepid" custom title="Chained campaigns that use flow">Chained&nbsp;campaigns</router-link>
          <router-link :to="'requests?flown_with=' + item.prepid" custom title="Requests flown with flow">Requests</router-link>
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
  name: 'flows',
  components: {
    ColumnSelector,
    DeletePrompt,
    ErrorDialog,
    Paginator,
  },
  mixins: [roleMixin, utilsMixin],
  data() {
    return {
      databaseName: 'flows',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: 1, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: 1 },
        { dbName: 'history' },
        { dbName: 'notes', visible: 1 },
        { dbName: 'allowed_campaigns', visible: 1 },
        { dbName: 'approval', visible: 1 },
        { dbName: 'next_campaign' },
        { dbName: 'request_parameters' },
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
    toggleType: function(item) {
      axios
        .post('restapi/' + this.databaseName + '/type', {'prepid': item.prepid})
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
