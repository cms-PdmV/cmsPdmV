<template>
  <div style="float: right">
    <div class="paginator-item">
      <small>Showing</small> {{pageStart}} - {{pageEnd}} <small>of</small> {{totalRows}}
    </div>
    <div class="paginator-item">
      <small>Page size:</small>
    </div>
    <div class="button-group paginator-item">
      <button class="button-group-button" v-for="limit in limits" :key="limit" v-bind:class="[pageSize === limit ? 'clicked' : '']" v-on:click="pageSize = limit">{{limit}}</button>
    </div>
    <div class="button-group paginator-item">
      <button class="button-group-button" v-if="page > 0" v-on:click="page -= 1">
        Previous
      </button>
      <div class="button-group-button">
        Page {{page}}
      </div>
      <button class="button-group-button" v-if="page < (totalRows / pageSize - 1)" v-on:click="page += 1">
        Next
      </button>
    </div>
  </div>
</template>

<script>
  export default {
    props:{
      totalRows: {value: 0},
    },
    data () {
      return {
        pageSize: undefined,
        page: undefined,
        limits: [25, 50, 100]
      }
    },
    computed: {
      pageStart: function() {
        return this.totalRows == 0 ? 0 : this.page * this.pageSize + 1;
      },
      pageEnd: function() {
        return Math.min(this.totalRows, this.page * this.pageSize + this.pageSize);
      }
    },
    created () {
      let query = Object.assign({}, this.$route.query);
      if ('page' in query) {
        this.page = Math.max(0, parseInt(query['page']));
      } else {
        this.page = 0;
      }
      if ('limit' in query) {
        // Not less than 1 not more than max limit
        this.pageSize = Math.max(1, parseInt(query['limit']));
        this.pageSize = Math.min(this.pageSize, this.limits[this.limits.length - 1]);
      } else {
        this.pageSize = this.limits[0];
      }
      query['page'] = this.page;
      query['limit'] = this.pageSize;
      this.$router.replace({query: query}).catch(() => {});
      this.$emit('update', this.page, this.pageSize);
    },
    watch:{
      pageSize: function (newValue, oldValue) {
        if (oldValue !== undefined) {
          this.updateQuery();
          this.$emit('update', this.page, newValue);
        }
      },
      page: function (newValue, oldValue) {
        if (oldValue !== undefined) {
          this.updateQuery();
          this.$emit('update', newValue, this.pageSize);
        }
      },
      '$route': function(to, from) {
        if (from.path != to.path) {
          this.page = 0;
          this.limit = this.limits[0];
        } else {
          let newQuery = Object.fromEntries(Object.entries(to.query));
          let oldQuery = Object.fromEntries(Object.entries(from.query));
          if (newQuery.page === undefined) {
            this.page = 0;
          }
          if (newQuery.limit === undefined) {
            this.pageSize = parseInt(oldQuery.limit);
          }
        }
        this.updateQuery();
      }
    },
    methods: {
      updateQuery: function(name, value) {
        let query = Object.assign({}, this.$route.query);
        if (query.page == this.page && query.limit == this.pageSize) {
          return;
        }
        query['page'] = this.page;
        query['limit'] = this.pageSize;
        this.$router.replace({query: query}).catch(() => {});
      }
    }
  }
</script>

<style scoped>
.paginator-item {
  margin: 8px 4px;
  height: 26px;
  display: inline-block;
  padding: 0;
  vertical-align: top;
  line-height: 26px;
  overflow: hidden;
}
.button-group {
  border-radius: 6px;
  border: solid 1px #aaa;
  color: var(--v-accent-base);
}
.button-group-button {
  display: inline-block;
  padding: 6px 6px;
  line-height: 14px;
  height: 26px;
}
.button-group-button:not(:first-child) {
  border-left: solid 1px #aaa;
}
.clicked {
  background-color: var(--v-accent-base);
  color: white;
  font-weight: 500;
}
.display-inline-block {
  display: inline-block;
}
</style>
