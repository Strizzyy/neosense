MATCH (n)
WITH labels(n) as nodeLabels, keys(n) as nodeProperties, n
UNWIND nodeLabels as label
WITH label, collect(distinct nodeProperties) as allProps, collect(n) as nodes
WITH label, 
     reduce(props = [], p in allProps | props + [prop IN p | prop]) as unique_properties,
     nodes
RETURN 
    label as node_label,
    unique_properties as properties,
    size(nodes) as node_count,
    size(unique_properties) as property_count
ORDER BY label