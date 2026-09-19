# the remote tool surface (read + safe writes)

52 tools exposed over HTTP:
  add_channel
  add_contact
  add_deal
  add_document
  add_event
  add_experiment
  add_material
  add_post
  add_todo
  archive_todo
  assign
  claim_todo
  classify_todo
  company_list
  complete_todo
  deal_pipeline
  decide_event
  decision_scorecard
  document_diary
  document_read
  document_topics
  documents_list
  experiment_board
  funnel
  list_users
  log_deal_update
  log_decision
  log_experiment_result
  log_post_result
  log_session
  log_touch
  my_work
  opener_context
  outbox_queue
  predict
  prepare_routine
  recent_changes
  record_click
  routines_board
  run_routine
  score_post
  search
  segment_360
  stage_outbox
  tick_routine
  todos_area
  todos_now
  update_document
  update_todo
  what_changed
  who_to_call
  who_to_reach

# destructive tools are NOT on the remote surface (stay on local stdio)

  add_advisor: exposed=False
  approve_outbox: exposed=False
  create_backup: exposed=False
  reindex_search: exposed=False
  remove_advisor: exposed=False
  remove_document: exposed=False
  update_advisor: exposed=False
