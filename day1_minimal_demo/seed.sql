INSERT INTO majors (major_id, major_name, department) VALUES
    (1, '软件工程', '计算机学院'),
    (2, '计算机科学与技术', '计算机学院'),
    (3, '数据科学与大数据技术', '人工智能学院');

INSERT INTO students
    (student_id, student_name, gender, enrollment_year, major_id)
VALUES
    (1, '张三', '男', 2023, 1),
    (2, '李四', '女', 2023, 2),
    (3, '王五', '女', 2022, 3),
    (4, '赵六', '男', 2023, 1),
    (5, '孙七', '女', 2022, 2);

INSERT INTO scores (score_id, student_id, course_name, score) VALUES
    (1, 1, '数据库原理', 92),
    (2, 1, '数据结构', 88),
    (3, 2, '数据库原理', 84),
    (4, 2, '数据结构', 80),
    (5, 3, '数据库原理', 95),
    (6, 3, '数据结构', 91),
    (7, 4, '数据库原理', 90),
    (8, 4, '数据结构', 86),
    (9, 5, '数据库原理', 78),
    (10, 5, '数据结构', 72);

