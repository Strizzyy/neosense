MATCH (n)
WITH labels(n)[0] as label, n
WITH label, collect(n) as nodes
WITH label, nodes, head(nodes) as sample_node
UNWIND keys(sample_node) as property_key
WITH label, property_key, sample_node[property_key] as sample_value, size(nodes) as total_count
RETURN 
    label,
    property_key,
    apoc.meta.type(sample_value) as data_type,
    sample_value as sample_value,
    total_count
ORDER BY label, property_key