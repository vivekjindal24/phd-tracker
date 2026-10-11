package edu.university.phdtracker.repository;

import edu.university.phdtracker.entity.Meeting;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface MeetingRepository extends JpaRepository<Meeting, Long> {

    List<Meeting> findBySupervisorId(Long supervisorId);

    List<Meeting> findByStudentId(Long studentId);
}

