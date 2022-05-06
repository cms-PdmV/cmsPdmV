export const sortingMixin = {

  created() {
    let query = Object.assign({}, this.$route.query);
    if ('sort' in query) {
      this.optionsSync.sortBy = [query['sort']];
    }
    if ('sort_asc' in query) {
      this.optionsSync.sortDesc = [query['sort_asc'] == 'true'];
    }
  },
  methods: {
    handleSort(query, oldOptions, newOptions) {
      if (!oldOptions.sortBy || !oldOptions.sortDesc || !newOptions.sortBy || !newOptions.sortDesc) {
        return;
      }
      let oldSortBy = undefined;
      if (oldOptions.sortBy.length) {
        oldSortBy = oldOptions.sortBy[0];
      }
      let oldSortAsc = undefined;
      if (oldOptions.sortDesc.length) {
        oldSortAsc = oldOptions.sortDesc[0];
      }
      let sortBy = undefined;
      if (newOptions.sortBy.length) {
        sortBy = newOptions.sortBy[0];
      }
      let sortAsc = undefined;
      if (newOptions.sortDesc.length) {
        sortAsc = newOptions.sortDesc[0];
      }
      if (oldSortBy === sortBy && oldSortAsc === sortAsc) {
        return;
      }
      if (sortBy !== undefined) {
        if (sortBy == 'history') {
          query['sort'] = 'created';
        } else {
          query['sort'] = sortBy;
        }
      } else {
        delete query['sort']
      }
      if (sortAsc !== undefined) {
        query['sort_asc'] = sortAsc ? 'true' : 'false';
      } else {
        delete query['sort_asc']
      }
    },
  },
};
