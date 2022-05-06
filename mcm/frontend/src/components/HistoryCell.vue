<template>
  <div>
    <table class="history" v-if="data && data.length > 0">
      <tr>
        <th>Time</th>
        <th>User</th>
        <th>Action</th>
        <th>Value</th>
      </tr>
      <tr>
        <td>{{dateFix(data[0].updater.submission_date)}}</td>
        <td>{{data[0].updater.author_name}}</td>
        <td>{{data[0].action}}</td>
        <td>{{data[0].step}}</td>
      </tr>
      <tr v-if="visibleItems < totalItems">
        <td colspan="4" @click="showMore()" class="show-more">Show more ({{this.visibleItems}}/{{this.totalItems}})</td>
      </tr>
      <tr v-for="(entry, index) in arrayOfVisibleItems" :key="index + ':' + entry.updater.submission_date">
        <td>{{dateFix(entry.updater.submission_date)}}</td>
        <td>{{entry.updater.author_name}}</td>
        <td>{{entry.action}}</td>
        <td>{{entry.step}}</td>
      </tr>
      <tr v-if="visibleItems >= totalItems && totalItems > this.initial + 1">
        <td colspan="4" @click="resetVisible()" class="show-more">Show less</td>
      </tr>
    </table>
  </div>
</template>

<script>
export default {
  props:{
    data: {
      type: Array,
    }
  },
  data() {
    return {
      totalItems: 0,
      visibleItems: 0,
      initial: 3,
      more: 10,
    };
  },
  computed: {
    arrayOfVisibleItems() {
      return this.data.slice(this.totalItems - (this.visibleItems - 1), this.totalItems);
    },
  },
  watch: {
    data: {
      handler(newValue) {
        this.totalItems = newValue.length;
        this.resetVisible();
      },
      deep: true,
    },
  },
  created() {
    this.totalItems = this.data.length;
    this.resetVisible();
  },
  methods: {
    showMore: function() {
      this.visibleItems = Math.min(this.totalItems, this.visibleItems + this.more);
      if (this.visibleItems > this.totalItems - 3) {
        this.visibleItems = this.totalItems;
      }
    },
    dateFix: function(date) {
      if (!date || date.length < 16) {
        return date;
      }
      return date.slice(0, 10) + ' ' + date.slice(11, 16).replace('-', ':');
    },
    resetVisible: function() {
      this.visibleItems = Math.min(this.totalItems, this.initial);
      if (this.visibleItems > this.totalItems - 2) {
        this.visibleItems = this.totalItems;
      }
    }
  }
}
</script>

<style scoped>
.history, .history td, .history th {
  border: 1px solid rgba(0, 0, 0, 0.87) !important;
  border-collapse: collapse;
  padding: 2px 4px !important;
  line-height: 1em;
}
.history {
  margin-top: 4px;
  margin-bottom: 4px;
  font-size: 0.9em;
  white-space: nowrap;
  width: 100%;
  max-width: 555px;
}
.show-more {
  cursor: pointer;
  text-align: center;
  font-style: italic;
  color: var(--v-anchor-base);
}
</style>