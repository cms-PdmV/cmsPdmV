export const navigationMixin = {

  beforeRouteUpdate(to, from, next) {
    next();
    if (from.path === to.path) {
      const ignoreKeys = ['page', 'limit', 'sort', 'sort_on', 'shown'];
      let oldQuery = Object.fromEntries(Object.entries(from.query).filter(([key]) => !ignoreKeys.includes(key)));
      let newQuery = Object.fromEntries(Object.entries(to.query).filter(([key]) => !ignoreKeys.includes(key)));
      const oldKeys = Object.keys(oldQuery);
      const newKeys = Object.keys(newQuery);
      if (oldKeys.length != newKeys.length) {
        this.fetchObjects();
        return;
      }
      for (let key of oldKeys) {
        if (oldQuery[key] !== newQuery[key]) {
          this.fetchObjects();
          return;
        }
      }
    }
  },
};
