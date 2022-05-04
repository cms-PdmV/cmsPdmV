import axios from 'axios';

export const utilsMixin = {

  methods: {
    fetchItems(database) {
      const ignoreKeys = ['shown'];
      const query = Object.fromEntries(Object.entries(this.$route.query).filter(([key]) => !ignoreKeys.includes(key)));
      query.db_name = database;
      let urlQuery = new URLSearchParams(query).toString();
      if (urlQuery) {
        urlQuery = '?' + urlQuery;
        urlQuery = decodeURI(urlQuery);
      }
      urlQuery = 'search' + urlQuery;
      return axios.get(urlQuery);
    },
  },
};
