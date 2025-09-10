MATCH (source)-[r]->(target)
WITH 
    labels(source)[0] as source_label,
    type(r) as relationship_type,
    labels(target)[0] as target_label,
    keys(r) as rel_properties
RETURN 
    source_label + ' -[' + relationship_type + ']-> ' + target_label as pattern,
    relationship_type,
    source_label,
    target_label,
    collect(distinct rel_properties) as relationship_properties,
    count(*) as relationship_count
ORDER BY source_label, relationship_type, target_label