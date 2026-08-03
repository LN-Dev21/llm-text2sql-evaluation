PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS majors;

CREATE TABLE majors (
    major_id INTEGER PRIMARY KEY,
    major_name TEXT NOT NULL,
    department TEXT NOT NULL
);

CREATE TABLE students (
    student_id INTEGER PRIMARY KEY,
    student_name TEXT NOT NULL,
    gender TEXT NOT NULL,
    enrollment_year INTEGER NOT NULL,
    major_id INTEGER NOT NULL,
    FOREIGN KEY (major_id) REFERENCES majors(major_id)
);

CREATE TABLE scores (
    score_id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 100),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

