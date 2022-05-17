<template>
  <v-container>
    <h1 class="page-title">Home</h1>
    <v-card raised class="page-card pa-2">
      <ul>
        <li v-for="routeName in ['campaigns', 'flows', 'chained_campaigns', 'requests', 'chained_requests']" :key="routeName">
          <router-link class="bold-hover" :to="routeName" custom>{{ capitalizeName(routeName) }}</router-link>
        </li>
      </ul>
    </v-card>
  </v-container>
</template>

<script>
export default {
  name: 'home',
  data() {
    return {};
  },
  created() {},
  methods: {

    capitalizeName: function(name) {
      return name.charAt(0).toUpperCase() + name.slice(1).replaceAll('_', ' ');
    }

  },
};
</script>
