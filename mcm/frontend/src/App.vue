<template>
  <v-app>
    <v-app-bar app>
      <a href="" class="no-decoration">
        <v-toolbar-title class="headline">
          <span>McM</span>
        </v-toolbar-title>
      </a>
      <v-spacer></v-spacer>
      <template v-for="route in routes">
        <router-link :to="'/' + getRoutePath(route)" v-slot="{ navigate }" custom :key="getRouteName(route)">
          <v-btn text @click="navigate">
            <span>{{ getRouteName(route) }}</span>
          </v-btn>
        </router-link>
      </template>
      <v-spacer></v-spacer>
      <div v-if="user">
        <span :title="'Username: ' + user.username + '\nRole: ' + user.role"
          ><small>Logged in as</small> {{ user.user_name }}
        </span>
        <img class="role-star" :title="user.role" :src="userRolePicture" />
      </div>
    </v-app-bar>
    <v-main class="content-container">
      <router-view />
    </v-main>
  </v-app>
</template>

<script>
import { roleMixin } from './mixins/UserRoleMixin.js';
export default {
  name: 'App',
  mixins: [roleMixin],
  created() {
    this.fetchUserInfo();
  },
  computed: {
    userRolePicture: function () {
      const role = this.user.role;
      if (role === 'user') {
        return 'static/user_star.png';
      }
      if (role === 'mc_contact') {
        return 'static/contact_star.png';
      }
      if (role === 'generator_convener') {
        return 'static/gen_star.png';
      }
      if (role === 'production_manager') {
        return 'static/manager_star.png';
      }
      if (role === 'production_expert' || role === 'administrator') {
        return 'static/admin_star.png';
      }
      return 'static/invisible.png';
    },
    user() {
      return this.$store.getters.getUserInfo;
    },
    routes() {
      let routes = ['campaigns', 'flows', 'chained_campaigns', 'requests', 'chained_requests', ['mccms', 'MccM Tickets']];
      if (this.role('production_manager')) {
        routes.push('batches');
        routes.push('invalidations');
      }
      return routes;
    }
  },
  methods: {
    getRoutePath(route) {
      if (Array.isArray(route)) {
        return route[0];
      }
      return route;
    },
    getRouteName(route) {
      if (Array.isArray(route)) {
        return route[1];
      }
      return route.replace('_', ' ');
    },
  },
};
</script>

<style scoped>
header {
  background: var(--v-background-base) !important;
}
.content-container {
  background: var(--v-backBackground-base);
  margin-bottom: 46px;
}
.headline {
  color: rgba(0, 0, 0, 0.87) !important;
}
a.no-decoration {
  text-decoration: none;
}
.role-star {
  width: 16px;
  height: 16px;
}
</style>

<style>
.v-data-table__wrapper,
.v-data-table__wrapper > table,
.v-data-table,
.content-container,
.v-application,
.v-application > div {
  min-width: 100%;
  width: fit-content !important;
}

.page-header {
  width: calc(100vw - 16px); /* Ugly fix */
  max-width: 100%;
  position: sticky;
  left: 0;
}

.page-title {
  margin: 4px 8px;
  text-overflow: ellipsis;
  overflow-x: hidden;
}

footer {
  padding: 0 12px;
  height: 42px;
  left: 0px;
  right: 0px;
  bottom: 0px;
  position: fixed;
  background: var(--v-background-base) !important;
  box-shadow: 0px -2px 4px -1px rgba(0, 0, 0, 0.2), 0px -4px 5px 0px rgba(0, 0, 0, 0.14),
    0px -1px 10px 0px rgba(0, 0, 0, 0.12);
}

.bold-hover,
.actions > a {
  text-decoration: none;
  margin-left: 2px;
  margin-right: 2px;
}

.bold-hover:hover,
.actions > a:hover {
  text-decoration: underline;
  /* text-shadow: .25px 0px .1px, -.25px 0px .1px; */
}

.notes {
  max-width: 450px;
  min-width: 350px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.25em;
  background: rgba(255,255,0,0.15);
  border: 1px solid gray;
  margin: 4px;
  padding: 2px;
  font-family: 'Schoolbell', monospace;
}

th {
  white-space: nowrap;
}

table.edit-table {
  width: 100%;
}

.edit-table td {
  padding-top: 8px;
  padding-bottom: 8px;
}

.edit-table input,
.edit-table select,
.edit-table textarea {
  width: 100%;
  border: 1px solid black;
  border-radius: 4px;
  padding: 0 4px;
}

.edit-table textarea {
  min-height: 200px;
  margin-bottom: -7px;
}

.edit-table input[type="number"] {
  width: 45%;
  text-align: right;
  padding: 0 0 0 4px;
  margin-right: 4px;
}

.edit-table input[type="checkbox"] {
  width: unset;
}

.edit-table select {
  width: 45%;
  height: 25.625px;
  appearance: menulist;
  padding: 0 4px;
}

.edit-table input:disabled,
.edit-table select:disabled,
.edit-table textarea:disabled {
  background: #dadada !important;
  color: rgba(0, 0, 0, 0.65);
  cursor: not-allowed;
  opacity: 1;
}

.edit-table tr td:first-child {
  white-space: nowrap;
  text-align: right;
  padding-right: 16px;
}
.edit-table tr td:last-child {
  width: 100%;
}

.edit-table tr:hover {
  background: #eee;
}

.sequence-field {
  font-family: monospace;
  font-size: 0.9em;
  padding: 4px;
  background: #fafafa;
  border: rgba(0, 0, 0, 0.87) 1px solid;
  border-radius: 4px;
  margin-bottom: 2px;
}

footer > button {
  margin-top: 7px;
}

</style>
