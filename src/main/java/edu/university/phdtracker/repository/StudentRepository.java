package edu.university.phdtracker.repository;

import edu.university.phdtracker.entity.Student;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface StudentRepository extends JpaRepository<Student, Long> {

    List<Student> findBySupervisorId(Long supervisorId);

    Optional<Student> findByUserId(Long userId);

    boolean existsByUserId(Long userId);
}
