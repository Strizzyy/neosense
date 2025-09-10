MATCH (n)
WITH labels(n)[0] as label, count(n) as node_count
WITH collect({label: label, count: node_count}) as node_stats
MATCH ()-[r]->()
WITH node_stats, type(r) as rel_type, count(r) as rel_count
WITH node_stats, collect({type: rel_type, count: rel_count}) as rel_stats
CALL db.propertyKeys() YIELD propertyKey
WITH node_stats, rel_stats, collect(propertyKey) as all_properties
RETURN {
    node_statistics: node_stats,
    relationship_statistics: rel_stats,
    total_properties: size(all_properties),
    property_keys: all_properties
} as database_statistics