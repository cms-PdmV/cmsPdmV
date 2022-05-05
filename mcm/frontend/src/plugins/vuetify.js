import Vue from 'vue';
import Vuetify from 'vuetify/lib/framework';

Vue.use(Vuetify);

export default new Vuetify({
  theme: {
      options: {
        customProperties: true,
      },
    themes: {
      light: {
        primary: '#005EB6',
        secondary: '#424242',
        accent: '#005EB6',
        anchor: '#005EB6',
        error: '#FF5252',
        info: '#2196F3',
        success: '#4CAF50',
        warning: '#FFC107',
        backBackground: '#FAFAFA',
        background: '#FFFFFF'
      },
    },
  },
  icons: {
    iconfont: 'mdi',
  },
});