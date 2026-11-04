# MCP tools

list_materials: ['lane', 'title', 'topic', 'type']
list_channels: ['name', 'platform']
list_posts: ['channel_id', 'material_id', 'platform', 'status']

# API reads agree with the module

GET /api/materials -> 40 rows
GET /api/channels?platform=linkedin -> 1 rows
GET /api/posts?status=posted -> 88 rows
