import Vue from 'vue';
import App from './App.vue';
import router from './router';
import vuetify from './plugins/vuetify';
import linkify from 'vue-linkify';
import sanitizeHTML from 'sanitize-html';
import Vuex from 'vuex';

Vue.config.productionTip = false;
Vue.directive('linkified', linkify);
Vue.prototype.sanitize = sanitizeHTML;
Vue.use(Vuex);

const store = new Vuex.Store({
  state: {
    user: undefined,
  },
  mutations: {
    setUserInfo(state, user) {
      state.user = user;
    },
  },
  getters: {
    getUserInfo(state) {
      return state.user;
    },
  },
});

new Vue({
  router,
  vuetify,
  render: h => h(App),
  store: store,
}).$mount('#app');
