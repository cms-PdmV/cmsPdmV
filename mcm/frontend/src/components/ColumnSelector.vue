<template>
  <v-card class="ma-2 pa-2">
    <h4>Columns</h4>
    <v-row style="margin: 2px">
      <v-col
        style="padding: 2px"
        cols="12"
        sm="6"
        md="3"
        lg="2"
        v-for="columnInfo in columnsLocalWithoutPrepID"
        :key="columnInfo.dbName"
      >
        <v-checkbox
          :label="columnInfo.displayName"
          v-model="columnInfo.visible"
          hide-details
          class="shrink checkbox-margin"
        ></v-checkbox>
      </v-col>
    </v-row>
  </v-card>
</template>

<script>
export default {
  props: {
    columns: {
      type: Array,
      value: [],
    },
  },
  data() {
    return {
      columnsLocal: this.columns,
      headers: [],
      shown: 0,
    };
  },
  created() {
    const query = Object.assign({}, this.$route.query);
    if (!('shown' in query)) {
      this.updateShownFromVisible();
      query.shown = this.shown;
    } else {
      this.shown = query.shown;
    }
    this.updateVisibleFromShown();
    this.$router.replace({ query: query }).catch(() => {});
  },
  watch: {
    columnsLocal: {
      handler: function() {
        this.updateShownFromVisible();
        this.updateTableHeaders();
      },
      deep: true,
    },
  },
  computed: {
    columnsLocalWithoutPrepID: function() {
      return this.columnsLocal.filter((entry) => entry.dbName !== 'prepid');
    },
  },
  methods: {
    updateTableHeaders: function() {
      this.headers = [];
      this.columnsLocal.forEach((entry) => {
        if (entry.visible || entry.dbName === 'prepid') {
          this.headers.push({ text: entry.displayName, value: entry.dbName, sortable: !!entry.sortable });
        }
      });
      this.$emit('updateColumns', this.columnsLocal, this.headers);
    },
    updateVisibleFromShown: function() {
      let shown = this.shown;
      this.columnsLocal.forEach((entry) => {
        entry.visible = (shown & 1) !== 0;
        shown = shown >> 1;
      });
    },
    updateShownFromVisible: function() {
      let shown = 0;
      this.columnsLocal
        .slice()
        .reverse()
        .forEach((entry) => {
          shown = shown << 1;
          if (entry.visible || entry.dbName === 'prepid') {
            shown = shown | 1;
          }
        });
      this.shown = shown;
      this.updateQuery('shown', this.shown);
    },
    updateQuery: function(name, value) {
      const query = Object.assign({}, this.$route.query);
      query[name] = value;
      this.$router.replace({ query: query }).catch(() => {});
    },
  },
};
</script>

<style scoped>
.checkbox-margin {
  margin: 0 !important;
  padding: 0 !important;
}
</style>
