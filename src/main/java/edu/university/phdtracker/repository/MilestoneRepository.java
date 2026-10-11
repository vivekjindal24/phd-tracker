package edu.university.phdtracker.repository;

import edu.university.phdtracker.entity.Milestone;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface MilestoneRepository extends JpaRepository<Milestone, Long> {

    List<Milestone> findByStudentId(Long studentId);
}

