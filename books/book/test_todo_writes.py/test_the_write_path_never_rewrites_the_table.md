# update, complete, archive, reorder, claim, append on the fake engine

(FakeAito.delete_table/create_table raise if any of these touch the table)
td-1 status=ready sort_order=1 owner=me title='renamed'
td-2 status=done sort_order=2 owner=None title='task td-2'
td-3 status=archived sort_order=0 owner=None title='task td-3'
