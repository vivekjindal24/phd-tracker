package edu.university.phdtracker.repository;

import edu.university.phdtracker.entity.Document;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DocumentRepository extends JpaRepository<Document, Long> {

    List<Document> findByStudentId(Long studentId);
}

