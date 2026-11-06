# Each fact and its source

  fact:sfa004: call:call-seed-0910 -> external
  fact:sfa001: doc:sdc009 -> linked (document:sdc009)
  fact:sfa006: touch:st067 -> linked (touch:st067)
  fact:sfa005: call:call-seed-0910 -> external
  fact:sfa008: doc:sdc009 -> linked (document:sdc009)
  fact:sfa010: call:call-seed-0304 -> external
  fact:sfa007: mail:mail-seed-0211 -> external
  fact:sfa002: call:call-seed-0111 -> external
  fact:sfa009: mail:mail-seed-0303 -> external
  fact:sfa003: mail:mail-seed-0211 -> external

# add_fact with a source that isn't stored: accepted, warned, drawn dangling

  warnings: ['source doc:doc-nope not found']
  in the unfold: dangling

# A call logged as a touch links to it

  call -> True
  a mail source warns: []
