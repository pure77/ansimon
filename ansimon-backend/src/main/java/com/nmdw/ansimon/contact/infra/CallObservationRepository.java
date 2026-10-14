package com.nmdw.ansimon.contact.infra;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;

public interface CallObservationRepository extends JpaRepository<CallObservation, Long> {

    boolean existsByContactJobId(Long contactJobId);

    /**
     * 목록 화면이 어르신 이름과 대응계획 문구까지 한 번에 그리므로 연관 엔티티를 fetch join으로 함께 읽습니다.
     * 조건은 모두 선택 항목이라 null이면 필터를 걸지 않습니다.
     */
    @Query(value = """
            select o from CallObservation o
            join fetch o.contactJob j
            join fetch j.elderly e
            join fetch j.interventionPlan p
            where (:elderlyId is null or e.id = :elderlyId)
              and (:status is null or o.contactStatus = :status)
              and (:from is null or o.endedAt >= :from)
              and (:to is null or o.endedAt < :to)
            order by o.endedAt desc
            """,
            countQuery = """
            select count(o) from CallObservation o
            where (:elderlyId is null or o.contactJob.elderly.id = :elderlyId)
              and (:status is null or o.contactStatus = :status)
              and (:from is null or o.endedAt >= :from)
              and (:to is null or o.endedAt < :to)
            """)
    Page<CallObservation> search(@Param("elderlyId") Long elderlyId,
                                 @Param("status") ContactStatus status,
                                 @Param("from") Instant from,
                                 @Param("to") Instant to,
                                 Pageable pageable);
}
