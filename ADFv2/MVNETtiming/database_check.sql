SELECT s.session_id, c.client_net_address AS [Client IP Address], s.host_name AS [Host Name], c.connect_time AS [Connection Time], r.command AS [Command], t.text AS [SQL Text], ts.last_request_start_time, ts.last_request_end_time, tc.last_read, tc.last_write 
FROM sys.dm_exec_sessions AS s 
JOIN sys.dm_exec_connections AS c ON s.session_id = c.session_id
CROSS APPLY sys.dm_exec_sql_text(c.most_recent_sql_handle) AS t
JOIN sys.dm_exec_requests AS r ON s.session_id = r.session_id
WHERE s.is_user_process = 1 and t.text like 'insert%'
ORDER BY s.session_id;
