package edu.university.phdtracker.repository;

import edu.university.phdtracker.entity.Supervisor;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface SupervisorRepository extends JpaRepository<Supervisor, Long> {

    Optional<Supervisor> findByUserId(Long userId);

    boolean existsByUserId(Long userId);
}
