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
      console.log(urlQuery);
      return axios.get(urlQuery);
    },
    checkAttributes(columns, items) {
      columns = columns.map(x => x.dbName);
      for (const item of items) {
        const ignore = ['_id', '_rev', '_actions'];
        let surplus = Object.keys(item).filter(x => !columns.includes(x)).filter(x => !ignore.includes(x)).join(', ');
        let missing = columns.filter(x => !Object.keys(item).includes(x)).filter(x => !ignore.includes(x)).join(', ');
        if (surplus.length) {
          console.warn(`${item.prepid} no columns: ${surplus}`);
        }
        if (missing.length) {
          console.warn(`${item.prepid} no attributes: ${missing}`);
        }
      }

    },
    dasLink(dataset) {
      return 'https://cmsweb.cern.ch/das/request?input=' + dataset;
    },
  },
};
