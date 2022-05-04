<template>
  <div>
    <div>
      <div>
        <h1 class="page-title">Campaigns</h1>
        <ColumnSelector :columns="columns" v-on:updateColumns="updateTableColumns" />
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
          <router-link :to="'flows?contains=' + item.prepid" custom title="Flows that use campaign">Flows</router-link>
          <router-link :to="'chained_campaigns?contains=' + item.prepid" custom title="Chained campaigns that use campaign">Chained campaigns</router-link>
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
  </div>
</template>

<script>
import ColumnSelector from './ColumnSelector';
import DeletePrompt from './DeletePrompt.vue';
import ErrorDialog from './ErrorDialog.vue';
import { roleMixin } from '../mixins/UserRoleMixin.js';
import { utilsMixin } from '../mixins/UtilsMixin.js';

export default {
  name: 'campaigns',
  components: {
    ColumnSelector,
    DeletePrompt,
    ErrorDialog,
  },
  mixins: [roleMixin, utilsMixin],
  data() {
    return {
      databaseName: 'campaigns',
      columns: [
        { dbName: 'prepid', displayName: 'PrepID', visible: 1, sortable: true },
        { dbName: '_actions', displayName: 'Actions', visible: 1 },
        { dbName: 'cmssw_release', displayName: 'CMSSW Release', visible: 1 },
        { dbName: 'memory', displayName: 'Memory', visible: 1 },
        { dbName: 'status', displayName: 'Status', visible: 1 },
        { dbName: 'notes', displayName: 'Notes', visible: 1 },
      ],
      headers: [],
      items: [],
      loading: false,
    };
  },
  created() {
    this.fetchObjects();
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
            this.loading = false;
            console.log(items);
          },
          (error) => {
            console.log(error);
            this.loading = false;
          },
        )
        .catch((error) => {
          console.log(error);
          this.loading = false;
        });
    },
    updateTableColumns: function(columns, headers) {
      this.columns = columns;
      this.headers = headers;
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

<style scoped>

.actions > a {
  text-decoration: none;
  margin-left: 2px;
  margin-right: 2px;
}

.actions > a:hover {
  text-decoration: none;
  font-weight: 600;
}

</style>
