# What create_table sends, per table (sha256 of the canonical JSON)

  PUT /api/v2/schema/users                     type=collection 518421dc1856d4c2
  PUT /api/v2/schema/assignments               type=collection 67e8cf90b3f4f38e
  PUT /api/v2/schema/tokens                    type=collection fce565ed98c07356
  PUT /api/v2/schema/companies                 type=collection ea32ff344d419610
  PUT /api/v2/schema/contacts                  type=collection d818d50946705684
  PUT /api/v2/schema/touches                   type=collection e5d73683c90fa63a
  PUT /api/v2/schema/decisions                 type=collection f731c2db5b74cd75
  PUT /api/v2/schema/sessions                  type=collection e7f138e33325b15a
  PUT /api/v2/schema/materials                 type=collection b50e95f7b3380ed1
  PUT /api/v2/schema/channels                  type=collection 19aeb362982a1845
  PUT /api/v2/schema/posts                     type=collection ad814a3d3441d2bb
  PUT /api/v2/schema/todos                     type=collection 2bddd1f3fcc4d872
  PUT /api/v2/schema/deals                     type=collection 512ad1ac407dec58
  PUT /api/v2/schema/deal_events               type=collection 7e8726808ad32cf8
  PUT /api/v2/schema/experiments               type=collection 5928ca9f67b418b8
  PUT /api/v2/schema/events                    type=collection 7ac19c48d7e26e23
  PUT /api/v2/schema/routines                  type=collection 9a094d45ef55bfcb
  PUT /api/v2/schema/documents                 type=collection 72cb3d25ac124b7f
  PUT /api/v2/schema/chat_messages             type=collection 1f01b00f69811ce2
  PUT /api/v2/schema/changelog                 type=collection 9fec5699835f51af
  PUT /api/v2/schema/search_contexts           type=collection 224c2461d73f5df5
  PUT /api/v2/schema/search_impressions        type=collection 83b49a1a10e51468
  PUT /api/v2/schema/web_sessions              type=collection 7d48fb10b9d8f103
  PUT /api/v2/schema/web_visitors              type=collection fca72adfd992a8a5
  PUT /api/v2/schema/web_suppressed            type=collection df4fcc4f7052cf8c
  PUT /api/v2/schema/web_steps                 type=collection 5ca7301f7eda256a

# What schema.py declares

  ['collection']
