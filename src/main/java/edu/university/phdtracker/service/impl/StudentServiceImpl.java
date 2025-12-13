package edu.university.phdtracker.service.impl;

import edu.university.phdtracker.dto.DocumentResponse;
import edu.university.phdtracker.dto.DocumentUploadRequest;
import edu.university.phdtracker.dto.MilestoneResponse;
import edu.university.phdtracker.dto.MilestoneUpdateRequest;
import edu.university.phdtracker.dto.NotificationResponse;
import edu.university.phdtracker.entity.Document;
import edu.university.phdtracker.entity.Milestone;
import edu.university.phdtracker.entity.Notification;
import edu.university.phdtracker.entity.NotificationChannel;
import edu.university.phdtracker.entity.Student;
import edu.university.phdtracker.exception.PhdTrackerException;
import edu.university.phdtracker.exception.ResourceNotFoundException;
import edu.university.phdtracker.repository.DocumentRepository;
import edu.university.phdtracker.repository.MilestoneRepository;
import edu.university.phdtracker.repository.NotificationRepository;
import edu.university.phdtracker.repository.StudentRepository;
import edu.university.phdtracker.service.NotificationService;
import edu.university.phdtracker.service.StudentService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class StudentServiceImpl implements StudentService {

    private final StudentRepository studentRepository;
    private final MilestoneRepository milestoneRepository;
    private final DocumentRepository documentRepository;
    private final NotificationRepository notificationRepository;
    private final NotificationService notificationService;

    @Override
    public MilestoneResponse updateMilestoneProgress(Long studentUserId, Long milestoneId, MilestoneUpdateRequest request) {
        Student student = getStudentByUserId(studentUserId);
        Milestone milestone = milestoneRepository.findById(milestoneId)
                .orElseThrow(() -> new ResourceNotFoundException("Milestone not found"));
        if (!milestone.getStudent().getId().equals(student.getId())) {
            throw new PhdTrackerException("Milestone does not belong to student");
        }
        milestone.setTitle(request.title());
        milestone.setDescription(request.description());
        milestone.setStatus(request.status());
        milestoneRepository.save(milestone);
        return mapMilestone(milestone);
    }

    @Override
    public DocumentResponse uploadDocument(Long studentUserId, DocumentUploadRequest request) {
        Student student = getStudentByUserId(studentUserId);
        Document document = Document.builder()
                .student(student)
                .fileName(request.fileName())
                .version(request.version())
                .build();
        document = documentRepository.save(document);
        notificationService.notifyUser(student.getSupervisor().getUser(),
                "Student " + student.getUser().getName() + " uploaded " + document.getFileName(),
                NotificationChannel.EMAIL);
        notificationService.notifyUser(student.getUser(),
                "Document " + document.getFileName() + " uploaded successfully",
                NotificationChannel.WHATSAPP);
        return mapDocument(document);
    }

    @Override
    @Transactional(readOnly = true)
    public List<NotificationResponse> getNotifications(Long studentUserId) {
        Student student = getStudentByUserId(studentUserId);
        List<Notification> notifications = notificationRepository.findByUserIdOrderBySentAtDesc(student.getUser().getId());
        return notifications.stream()
                .map(this::mapNotification)
                .collect(Collectors.toList());
    }

    private Student getStudentByUserId(Long userId) {
        return studentRepository.findByUserId(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Student profile not found"));
    }

    private MilestoneResponse mapMilestone(Milestone milestone) {
        return new MilestoneResponse(
                milestone.getId(),
                milestone.getTitle(),
                milestone.getDescription(),
                milestone.getDeadline(),
                milestone.getStatus(),
                milestone.getCreatedAt()
        );
    }

    private DocumentResponse mapDocument(Document document) {
        return new DocumentResponse(
                document.getId(),
                document.getFileName(),
                document.getVersion(),
                document.getUploadedAt()
        );
    }

    private NotificationResponse mapNotification(Notification notification) {
        return new NotificationResponse(
                notification.getId(),
                notification.getMessage(),
                notification.getChannel(),
                notification.getSentAt()
        );
    }
}
