// If you change a function, who might break?
MATCH (target:Function {name: "connect"})
MATCH (dependent:Function)-[:CALLS*1..5]->(target)
RETURN DISTINCT dependent.name AS affected_function, dependent.file AS in_file
ORDER BY in_file, affected_function;

// See the whole graph
// MATCH (n)-[r]->(m) RETURN n, r, m;
