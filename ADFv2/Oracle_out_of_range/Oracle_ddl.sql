CREATE TABLE testrbadmin.Test_prod_issue (
        AAAAA varchar2(255)
      , BBBBB varchar2(255)
      , CCCCC timestamp(6)
      , DDDDD varchar2(255)
      , EEEEE varchar2(255)
      , FFFFF varchar2(255)
      , GGGGG varchar2(255)
      , HHHHH varchar2(255)
      , IIIII varchar2(255)
      , JJJJJ timestamp(6)
      , KKKKK NUMBER(38,18)
      , LLLLL varchar2(255)
      , MMMMM NUMBER(38,18)
      , NNNNN timestamp(6)
      , OOOO NUMBER(38,18)
      , PPPP varchar2(255)
      , QQQQ NUMBER(38,18)
      , RRRR timestamp(6)
    )
    COMPRESS FOR ALL OPERATIONS
    ENABLE ROW MOVEMENT
    PARALLEL (DEGREE DEFAULT);

INSERT INTO testrbadmin.Test_prod_issue
    (AAAAA, BBBBB, CCCCC, DDDDD, EEEEE, FFFFF, GGGGG, HHHHH, IIIII, JJJJJ, KKKKK, LLLLL, MMMMM, NNNNN, OOOO, PPPP, QQQQ, RRRR)
VALUES
    (RPAD('A', 255, 'A'), RPAD('B', 255, 'B'), CURRENT_TIMESTAMP AT TIME ZONE 'UTC', RPAD('D', 255, 'D'), RPAD('E', 255, 'E'), RPAD('F', 255, 'F'), RPAD('G', 255, 'G'), RPAD('H', 255, 'H'), RPAD('I', 255, 'I'), CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 99999999999999999999.999999999999999999, RPAD('L', 255, 'L'), 99999999999999999999.999999999999999999, CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 99999999999999999999.999999999999999999, RPAD('P', 255, 'P'), 99999999999999999999.999999999999999999, CURRENT_TIMESTAMP AT TIME ZONE 'UTC');