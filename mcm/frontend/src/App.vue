<template>
  <v-app>
    <v-app-bar app>
      <a href="" class="no-decoration">
        <v-toolbar-title class="headline">
          <span>McM</span>
        </v-toolbar-title>
      </a>
      <v-spacer></v-spacer>
      <template v-for="routeName in ['campaigns', 'flows', 'chained_campaigns', 'requests', 'chained_requests']">
        <router-link :to="routeName" v-slot="{ route, navigate }" custom :key="routeName">
          <v-btn text class="ml-1 mr-1" @click="navigate">
            <span>{{ route.name.replace('_', ' ') }}</span>
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

</style>
