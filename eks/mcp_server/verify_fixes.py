import data_retrieval_engine as dre
dre.load_database_schema_config('database_schema.json')
def mock_eq(sql, params): return [{'status':'ok'}]
dre.execute_query = mock_eq

session_with_company = {'site_id': [2223391], 'company_id': [1000241]}
session_site_only    = {'site_id': [2223391]}

tests = [
    ('BUG1 FIXED: Occupied units+user (company in session, NO t0.company_id in WHERE)',
        ['unit','user'], 'DATA_RETRIEVAL', ['inuse'], None, None, session_with_company,
        lambda sql: 't0.company_id' not in sql[sql.find('WHERE'):]),
    ('BUG2 FIXED: token "user" NOT resolved to type=user',
        ['unit','user'], 'DATA_RETRIEVAL', ['inuse','user'], None, None, session_with_company,
        lambda sql: "type = 'user'" not in sql),
    ('GOOD: company_id applied to users table (not units)',
        ['user'], 'DATA_RETRIEVAL', ['client'], None, None, session_with_company,
        lambda sql: 't0.company_id' in sql),
    ('GOOD: unit-only query no company_id',
        ['unit'], 'DATA_AGGREGATION', ['count','available'], None, None, session_with_company,
        lambda sql: 't0.company_id' not in sql),
    ('GOOD: employee routes to user.type in unit+user query',
        ['unit','user'], 'DATA_RETRIEVAL', ['inuse','employee'], None, None, session_with_company,
        lambda sql: "t1.type = 'employee'" in sql),
    ('GOOD: site manager type resolves correctly',
        ['user'], 'DATA_RETRIEVAL', ['site manager'], None, None, session_with_company,
        lambda sql: "type = 'site_manager'" in sql),
    ('GOOD: "standard user" phrase still resolves to type=user',
        ['user'], 'DATA_RETRIEVAL', ['standard user'], None, None, session_site_only,
        lambda sql: "type = 'user'" in sql),
    ('GOOD: overlock still resolves',
        ['unit'], 'DATA_AGGREGATION', ['count','overlock'], None, None, session_with_company,
        lambda sql: "rental_state = 'overlock'" in sql),
    ('GOOD: available still resolves',
        ['unit'], 'DATA_AGGREGATION', ['count','free'], None, None, session_with_company,
        lambda sql: "rental_state = 'available'" in sql),
    ('GOOD: noke admin resolves',
        ['user'], 'DATA_RETRIEVAL', ['noke admin'], None, None, session_with_company,
        lambda sql: "type = 'noke_admin'" in sql),
]

passed = failed = 0
for label, subjects, intent, filters, agg, search, session, check in tests:
    try:
        dre.run_compiled_mcp_query(
            subjects=subjects, intent_type=intent, session_context=session,
            semantic_filters=filters, aggregation_column=agg, search_keyword=search)
        sql = getattr(dre, 'LAST_COMPILED_SQL', '')
        where = sql[sql.find('WHERE'):].split(';')[0].strip()
        ok = check(sql)
        status = 'PASS' if ok else 'FAIL'
        if ok: passed += 1
        else:  failed += 1
        print(f'[{status}] {label}')
        print(f'         WHERE: {where[:120]}')
    except Exception as e:
        failed += 1
        print(f'[FAIL] {label}: {e}')
    print()

print(f'Result: {passed} passed, {failed} failed')
