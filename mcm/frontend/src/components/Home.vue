<template>
  <div>
    <h1 class="page-title">Home</h1>
    <v-card raised class="page-card"> </v-card>
    <ul>
      <li
        v-for="routeName in ['campaigns', 'flows', 'chained_campaigns', 'requests', 'chained_requests']"
        :key="routeName"
      >
        <router-link :to="routeName" custom>{{ routeName }}</router-link>
      </li>
    </ul>
  </div>
</template>

<script>
export default {
  name: 'home',
  data() {
    return {};
  },
  created() {},
  methods: {},
};
</script>
