import Vue from 'vue';
import VueRouter from 'vue-router';
import Home from '../components/Home.vue';

Vue.use(VueRouter);

const routes = [
  {
    path: '/',
    name: 'home',
    component: Home,
  },
  {
    path: '/campaigns',
    name: 'campaigns',
    // route level code-splitting
    // this generates a separate chunk (campaigns.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import('../components/Campaigns.vue'),
  },
  {
    path: '/flows',
    name: 'flows',
    component: () => import('../components/Flows.vue'),
  },
  {
    path: '/chained_campaigns',
    name: 'chained_campaigns',
    component: () => import('../components/ChainedCampaigns.vue'),
  },
  {
    path: '/requests',
    name: 'requests',
    component: () => import('../components/Requests.vue'),
  },
  {
    path: '/chained_requests',
    name: 'chained_requests',
    component: () => import('../components/ChainedRequests.vue'),
  },

  {
    path: '/campaigns/edit',
    name: 'campaigns_edit',
    component: () => import('../components/CampaignsEdit.vue'),
  },
  {
    path: '/flows/edit',
    name: 'flows_edit',
    component: () => import('../components/FlowsEdit.vue'),
  },
  {
    path: '/chained_campaigns/edit',
    name: 'chained_campaigns_edit',
    component: () => import('../components/ChainedCampaignsEdit.vue'),
  },
  {
    path: '/requests/edit',
    name: 'requests_edit',
    component: () => import('../components/RequestsEdit.vue'),
  },
];

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
});

export default router;
