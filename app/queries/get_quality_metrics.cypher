MATCH (n)
WITH labels(n)[0] as label, n
WITH label, collect(n) as nodes
RETURN 
    label,
    size(nodes) as total_nodes,
    size([node in nodes WHERE size(keys(node)) > 0]) as nodes_with_properties,
    size([node in nodes WHERE size(keys(node)) = 0]) as nodes_without_properties,
    round(100.0 * size([node in nodes WHERE size(keys(node)) > 0]) / size(nodes), 2) as property_coverage_percent
ORDER BY label