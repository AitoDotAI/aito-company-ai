# kpi=sandbox on the fixture day

  sessions 4, with the target 1, thin below 5
  dropped as definitionally linked: ['kpi_login_page', 'kpi_signup', 'kpi_data_loaded', 'kpi_first_query', 'kpi_api_keys']
  dropped as the target's own events: ['instance_create', 'instance_ready', 'sandbox_created']
  drivers: [('country', 'Germany', 1, True), ('hour', 9, 1, True), ('source', 'direct', 1, True), ('device_class', 'desktop', 2, True), ('landing_path', '/', 2, True), ('source', 'social', 2, True), ('weekday', 'mon', 4, True), ('country', 'Finland', 1, True), ('country', 'Sweden', 1, True), ('country', 'United States', 1, True)]
  other_kpis: [('kpi_contact_page', False, 4, True), ('kpi_pricing_page', False, 3, True), ('kpi_pricing_page', True, 1, True)]
  other_events: [('co_events', 'demo_signup_cta_clicked', 1, True), ('co_events', 'page:ecommerce.aito.ai/cart', 1, True), ('co_events', 'page:/', 2, True), ('co_events', 'page:/blog/every-screen-a-decision/', 1, True), ('co_events', 'page:/docs/', 1, True), ('co_events', 'page:/docs/api/v2/quickstart/', 1, True), ('co_events', 'page:/pricing/', 1, True), ('co_events', 'page:/signup/', 1, True)]

# Any event: event=demo_signup_cta_clicked

  with the target 1; own events dropped: ['demo_signup_cta_clicked']

# A target must be one KPI or one event

  {'kpi': 'nope'}: unknown kpi 'nope'; have ['api_keys', 'contact_page', 'data_loaded', 'first_query', 'login
  {}: give exactly one target: kpi or event
  {'kpi': 'sandbox', 'event': 'x'}: give exactly one target: kpi or event
