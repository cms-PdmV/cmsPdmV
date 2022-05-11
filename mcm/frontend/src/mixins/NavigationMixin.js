export const navigationMixin = {

  beforeRouteUpdate(to, from, next) {
    next();
    if (from.path === to.path) {
      const ignoreKeys = ['page', 'limit', 'sort', 'sort_on', 'shown'];
      let oldQuery = Object.fromEntries(Object.entries(from.query).filter(([key]) => !ignoreKeys.includes(key)));
      let newQuery = Object.fromEntries(Object.entries(to.query).filter(([key]) => !ignoreKeys.includes(key)));
      let oldQueryString = Object.keys(oldQuery).sort().map(key => `${key}=${oldQuery[key]}`).join('&');
      let newQueryString = Object.keys(newQuery).sort().map(key => `${key}=${newQuery[key]}`).join('&');
      if (oldQueryString != newQueryString) {
        this.fetchObjects();
      }
    }
  },
};
