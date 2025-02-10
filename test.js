var headers = $request.headers;
headers['x-header'] = 'NEW_HEADER_VALUE';  // 把这里的值改成你需要的

$done({ headers });
