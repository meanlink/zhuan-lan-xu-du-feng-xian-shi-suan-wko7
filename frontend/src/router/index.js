export function route(){const [page='overview',id]=location.hash.replace(/^#\//,'').split('/');return {page,id};}
