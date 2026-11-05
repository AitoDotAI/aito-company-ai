# MCP tools

list_materials: ['lane', 'title', 'topic', 'type']
list_channels: ['name', 'platform']
list_posts: ['channel_id', 'material_id', 'platform', 'status']

# API reads agree with the module

GET /api/materials -> 40 rows
GET /api/channels?platform=linkedin -> 1 rows
GET /api/posts?status=posted -> 88 rows

# A bad filter value is the caller's error: 400, not 500

GET /api/posts?status=maybe -> 400 {'error': "unknown status 'maybe'; allowed ['go', 'no_go', 'planned', 'posted']"}
GET /api/channels?platform=myspace -> 400 {'error': "unknown platform 'myspace'; allowed ['blog', 'hackernews', 'linkedin', 'reddit']"}
GET /api/materials?lane=lukewarm -> 400 {'error': "unknown lane 'lukewarm'; allowed ['cold', 'warm']"}
