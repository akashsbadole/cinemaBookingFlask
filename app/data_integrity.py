"""
Data Integrity Checks for Cinema Management System
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text, and_, or_, func
from app.database import db
from app.validators import ValidationError, BusinessValidators


class IntegrityChecker:
    """Base class for data integrity checks"""
    
    @staticmethod
    def check_referential_integrity():
        """Check referential integrity across all related tables"""
        issues = []
        
        try:
            # Check orphaned booking seats (booking seats without bookings)
            orphaned_booking_seats = db.session.execute(text("""
                SELECT bs.id 
                FROM booking_seats bs 
                LEFT JOIN bookings b ON bs.booking_id = b.id 
                WHERE b.id IS NULL
                LIMIT 10
            """)).fetchall()
            
            if orphaned_booking_seats:
                issues.append({
                    'type': 'orphaned_booking_seats',
                    'count': len(orphaned_booking_seats),
                    'message': f'Found {len(orphaned_booking_seats)} orphaned booking seat records',
                    'severity': 'high'
                })
            
            # Check orphaned payment audit records
            orphaned_audit_records = db.session.execute(text("""
                SELECT pa.id 
                FROM payment_audit pa 
                LEFT JOIN payments p ON pa.payment_id = p.id 
                WHERE p.id IS NULL
                LIMIT 10
            """)).fetchall()
            
            if orphaned_audit_records:
                issues.append({
                    'type': 'orphaned_payment_audit',
                    'count': len(orphaned_audit_records),
                    'message': f'Found {len(orphaned_audit_records)} orphaned payment audit records',
                    'severity': 'medium'
                })
            
            # Check bookings without payments (for confirmed bookings)
            bookings_without_payments = db.session.execute(text("""
                SELECT b.id, b.reference_number 
                FROM bookings b 
                LEFT JOIN payments p ON b.id = p.booking_id 
                WHERE b.status = 'confirmed' 
                AND p.id IS NULL
                AND b.booking_time < :cutoff_date
                LIMIT 10
            """), {'cutoff_date': datetime.now() - timedelta(days=1)}).fetchall()
            
            if bookings_without_payments:
                issues.append({
                    'type': 'bookings_without_payments',
                    'count': len(bookings_without_payments),
                    'details': [{'id': row[0], 'reference': row[1]} for row in bookings_without_payments],
                    'message': f'Found {len(bookings_without_payments)} confirmed bookings without payments',
                    'severity': 'high'
                })
            
            return issues
            
        except Exception as e:
            logging.error(f"Error checking referential integrity: {str(e)}")
            return [{'type': 'check_error', 'message': f'Integrity check failed: {str(e)}', 'severity': 'high'}]
    
    @staticmethod
    def check_business_constraints():
        """Check business rule compliance"""
        issues = []
        
        try:
            # Check shows with overlapping times
            overlapping_shows = db.session.execute(text("""
                SELECT s1.id, s1.show_date, s1.show_time, s1.screen_id,
                       s2.id as conflict_id, s2.show_time as conflict_time
                FROM shows s1
                JOIN shows s2 ON s1.screen_id = s2.screen_id 
                                   AND s1.show_date = s2.show_date
                                   AND s1.id < s2.id
                WHERE s1.show_date >= :current_date
                AND (
                    (s1.show_time <= s2.show_time AND s1.end_time > s2.show_time) OR
                    (s1.show_time < s2.show_time AND s1.end_time > s2.show_time) OR
                    (s1.show_time >= s2.show_time AND s1.show_time < s2.end_time)
                )
                LIMIT 5
            """), {'current_date': datetime.now().date()}).fetchall()
            
            if overlapping_shows:
                issues.append({
                    'type': 'overlapping_shows',
                    'count': len(overlapping_shows),
                    'details': overlapping_shows,
                    'message': f'Found {len(overlapping_shows)} shows with scheduling conflicts',
                    'severity': 'high'
                })
            
            # Check shows in past with future dates (data inconsistency)
            past_shows_future_dates = db.session.execute(text("""
                SELECT id, show_date, show_time 
                FROM shows 
                WHERE show_date > :current_date 
                AND show_date < :past_date 
                LIMIT 5
            """), {
                'current_date': datetime.now().date(),
                'past_date': datetime.now().date() - timedelta(days=7)
            }).fetchall()
            
            if past_shows_future_dates:
                issues.append({
                    'type': 'inconsistent_show_dates',
                    'count': len(past_shows_future_dates),
                    'details': past_shows_future_dates,
                    'message': f'Found {len(past_shows_future_dates)} shows with inconsistent date information',
                    'severity': 'medium'
                })
            
            # Check bookings for shows that have already started
            bookings_for_past_shows = db.session.execute(text("""
                SELECT b.id, b.reference_number, s.show_date, s.show_time
                FROM bookings b
                JOIN shows s ON b.show_id = s.id
                WHERE b.status = 'confirmed'
                AND (
                    (s.show_date < :current_date) OR 
                    (s.show_date = :current_date AND s.show_time < :current_time)
                )
                AND b.booking_time > :cutoff_time
                LIMIT 5
            """), {
                'current_date': datetime.now().date(),
                'current_time': datetime.now().time(),
                'cutoff_time': datetime.now() - timedelta(minutes=30)  # Allow 30 minutes after show start
            }).fetchall()
            
            if bookings_for_past_shows:
                issues.append({
                    'type': 'bookings_for_past_shows',
                    'count': len(bookings_for_past_shows),
                    'details': bookings_for_past_shows,
                    'message': f'Found {len(bookings_for_past_shows)} bookings for shows that have already started',
                    'severity': 'medium'
                })
            
            return issues
            
        except Exception as e:
            logging.error(f"Error checking business constraints: {str(e)}")
            return [{'type': 'check_error', 'message': f'Integrity check failed: {str(e)}', 'severity': 'high'}]
    
    @staticmethod
    def check_data_consistency():
        """Check data consistency across tables"""
        issues = []
        
        try:
            # Check payment amounts that don't match booking totals
            payment_booking_mismatches = db.session.execute(text("""
                SELECT p.id, p.amount, b.total_amount, b.reference_number
                FROM payments p
                JOIN bookings b ON p.booking_id = b.id
                WHERE p.status = 'completed'
                AND ABS(p.amount - b.total_amount) > 0.01
                LIMIT 10
            """)).fetchall()
            
            if payment_booking_mismatches:
                issues.append({
                    'type': 'payment_booking_mismatch',
                    'count': len(payment_booking_mismatches),
                    'details': payment_booking_mismatches,
                    'message': f'Found {len(payment_booking_mismatches)} payments with amounts not matching booking totals',
                    'severity': 'high'
                })
            
            # Check negative or zero amounts in payments
            invalid_payment_amounts = db.session.execute(text("""
                SELECT id, amount, reference_id
                FROM payments
                WHERE amount <= 0
                LIMIT 5
            """)).fetchall()
            
            if invalid_payment_amounts:
                issues.append({
                    'type': 'invalid_payment_amounts',
                    'count': len(invalid_payment_amounts),
                    'details': invalid_payment_amounts,
                    'message': f'Found {len(invalid_payment_amounts)} payments with invalid amounts (zero or negative)',
                    'severity': 'high'
                })
            
            # Check seats with invalid types
            invalid_seat_types = db.session.execute(text("""
                SELECT id, screen_id, row, column, type
                FROM seats
                WHERE type NOT IN ('normal', 'premium', 'vip')
                LIMIT 5
            """)).fetchall()
            
            if invalid_seat_types:
                issues.append({
                    'type': 'invalid_seat_types',
                    'count': len(invalid_seat_types),
                    'details': invalid_seat_types,
                    'message': f'Found {len(invalid_seat_types)} seats with invalid types',
                    'severity': 'medium'
                })
            
            return issues
            
        except Exception as e:
            logging.error(f"Error checking data consistency: {str(e)}")
            return [{'type': 'check_error', 'message': f'Integrity check failed: {str(e)}', 'severity': 'high'}]
    
    @staticmethod
    def check_performance_issues():
        """Check for performance-related data issues"""
        issues = []
        
        try:
            # Check shows with very low occupancy
            low_occupancy_shows = db.session.execute(text("""
                SELECT s.id, s.show_date, COUNT(bs.id) as seats_booked,
                       (SELECT COUNT(se.id) FROM seats WHERE se.screen_id = s.screen_id) as total_seats
                FROM shows s
                LEFT JOIN booking_seats bs ON s.id = bs.show_id
                LEFT JOIN bookings b ON bs.booking_id = b.id AND b.status = 'confirmed'
                WHERE s.show_date >= :start_date AND s.show_date <= :end_date
                AND s.show_date < :current_date
                GROUP BY s.id, s.show_date
                HAVING seats_booked < (total_seats * 0.1)  -- Less than 10% occupancy
                ORDER BY seats_booked ASC
                LIMIT 5
            """), {
                'start_date': datetime.now().date() - timedelta(days=30),
                'end_date': datetime.now().date() - timedelta(days=1),
                'current_date': datetime.now().date()
            }).fetchall()
            
            if low_occupancy_shows:
                issues.append({
                    'type': 'low_occupancy_shows',
                    'count': len(low_occupancy_shows),
                    'details': low_occupancy_shows,
                    'message': f'Found {len(low_occupancy_shows)} shows with very low occupancy (< 10%)',
                    'severity': 'low'
                })
            
            # Check movies without any shows
            movies_without_shows = db.session.execute(text("""
                SELECT m.id, m.name, m.status
                FROM movies m
                LEFT JOIN shows s ON m.id = s.movie_id
                WHERE s.id IS NULL
                AND m.status = 'active'
                AND m.created_at < :cutoff_date
                LIMIT 5
            """), {'cutoff_date': datetime.now() - timedelta(days=7)}).fetchall()
            
            if movies_without_shows:
                issues.append({
                    'type': 'movies_without_shows',
                    'count': len(movies_without_shows),
                    'details': movies_without_shows,
                    'message': f'Found {len(movies_without_shows)} active movies without any scheduled shows',
                    'severity': 'medium'
                })
            
            return issues
            
        except Exception as e:
            logging.error(f"Error checking performance issues: {str(e)}")
            return [{'type': 'check_error', 'message': f'Integrity check failed: {str(e)}', 'severity': 'high'}]
    
    @staticmethod
    def check_security_vulnerabilities():
        """Check for potential security vulnerabilities in data"""
        issues = []
        
        try:
            # Check for users with weak passwords
            users_with_weak_passwords = db.session.execute(text("""
                SELECT id, username, email
                FROM users
                WHERE password_hash LIKE 'sha256$%'  -- Simple SHA256 without salt
                   OR password_hash LIKE 'md5$%'      -- Old MD5 without salt
                   OR LENGTH(password) < 32        -- Too short hashes
                LIMIT 5
            """)).fetchall()
            
            if users_with_weak_passwords:
                issues.append({
                    'type': 'weak_password_hashes',
                    'count': len(users_with_weak_passwords),
                    'details': users_with_weak_passwords,
                    'message': f'Found {len(users_with_weak_passwords)} users with potentially weak password hashes',
                    'severity': 'high'
                })
            
            # Check for admin accounts without recent activity
            inactive_admins = db.session.execute(text("""
                SELECT id, username, last_login
                FROM users
                WHERE role = 'admin'
                AND (last_login IS NULL OR last_login < :cutoff_date)
                LIMIT 5
            """), {'cutoff_date': datetime.now() - timedelta(days=90)}).fetchall()
            
            if inactive_admins:
                issues.append({
                    'type': 'inactive_admin_accounts',
                    'count': len(inactive_admins),
                    'details': inactive_admins,
                    'message': f'Found {len(inactive_admins)} admin accounts without recent login activity',
                    'severity': 'medium'
                })
            
            return issues
            
        except Exception as e:
            logging.error(f"Error checking security vulnerabilities: {str(e)}")
            return [{'type': 'check_error', 'message': f'Integrity check failed: {str(e)}', 'severity': 'high'}]
    
    @staticmethod
    def run_all_checks():
        """Run all integrity checks and return a consolidated report"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {}
        }
        
        # Run all check types
        check_methods = [
            ('referential_integrity', IntegrityChecker.check_referential_integrity),
            ('business_constraints', IntegrityChecker.check_business_constraints),
            ('data_consistency', IntegrityChecker.check_data_consistency),
            ('performance_issues', IntegrityChecker.check_performance_issues),
            ('security_vulnerabilities', IntegrityChecker.check_security_vulnerabilities)
        ]
        
        total_issues = 0
        total_high = 0
        total_medium = 0
        total_low = 0
        
        for check_name, check_method in check_methods:
            try:
                issues = check_method()
                results['checks'][check_name] = {
                    'status': 'completed',
                    'issues': issues,
                    'count': len(issues)
                }
                
                # Count severity levels
                for issue in issues:
                    total_issues += 1
                    if issue.get('severity') == 'high':
                        total_high += 1
                    elif issue.get('severity') == 'medium':
                        total_medium += 1
                    elif issue.get('severity') == 'low':
                        total_low += 1
                        
            except Exception as e:
                results['checks'][check_name] = {
                    'status': 'failed',
                    'error': str(e),
                    'issues': []
                }
                logging.error(f"Integrity check {check_name} failed: {str(e)}")
        
        # Add summary
        results['summary'] = {
            'total_issues': total_issues,
            'high_severity': total_high,
            'medium_severity': total_medium,
            'low_severity': total_low,
            'overall_status': 'healthy' if total_high == 0 else 'needs_attention'
        }
        
        return results
    
    @staticmethod
    def fix_orphaned_records():
        """Attempt to fix common orphaned record issues"""
        fixes_applied = []
        
        try:
            # Delete orphaned booking seats
            orphaned_seats_deleted = db.session.execute(text("""
                DELETE FROM booking_seats 
                WHERE booking_id NOT IN (SELECT id FROM bookings)
            """))
            
            if orphaned_seats_deleted > 0:
                fixes_applied.append({
                    'type': 'deleted_orphaned_booking_seats',
                    'count': orphaned_seats_deleted,
                    'message': f'Deleted {orphaned_seats_deleted} orphaned booking seat records'
                })
            
            # Delete orphaned payment audit records
            orphaned_audit_deleted = db.session.execute(text("""
                DELETE FROM payment_audit 
                WHERE payment_id NOT IN (SELECT id FROM payments)
            """))
            
            if orphaned_audit_deleted > 0:
                fixes_applied.append({
                    'type': 'deleted_orphaned_payment_audit',
                    'count': orphaned_audit_deleted,
                    'message': f'Deleted {orphaned_audit_deleted} orphaned payment audit records'
                })
            
            # Commit changes
            db.session.commit()
            
            return {
                'status': 'completed',
                'fixes_applied': fixes_applied,
                'message': f'Applied {len(fixes_applied)} automated fixes'
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error fixing orphaned records: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'message': 'Failed to apply automated fixes'
            }


class ConcurrentAccessChecker:
    """Handle concurrent access issues"""
    
    @staticmethod
    def check_booking_conflicts(show_id, seat_ids, user_id, exclude_booking_id=None):
        """Check for potential concurrent booking conflicts"""
        from app.bookings.models import Booking, BookingSeat
        
        try:
            # Check for existing seat locks or bookings
            query = db.session.query(BookingSeat).join(Booking).filter(
                Booking.show_id == show_id,
                BookingSeat.seat_id.in_(seat_ids),
                Booking.status.in_(['confirmed', 'pending'])
            )
            
            # Exclude current booking if editing
            if exclude_booking_id:
                query = query.filter(Booking.id != exclude_booking_id)
            
            # Check for recent activity (within last 5 minutes)
            recent_time = datetime.utcnow() - timedelta(minutes=5)
            query = query.filter(Booking.booking_time >= recent_time)
            
            conflicting_bookings = query.all()
            
            if conflicting_bookings:
                return {
                    'has_conflict': True,
                    'conflicts': [
                        {
                            'booking_id': b.id,
                            'seat_ids': [bs.seat_id for bs in b.booking_seats],
                            'user_id': b.user_id,
                            'booking_time': b.booking_time
                        }
                        for b in conflicting_bookings
                    ],
                    'message': f'Seats are already being booked by other users'
                }
            
            return {'has_conflict': False}
            
        except Exception as e:
            logging.error(f"Error checking booking conflicts: {str(e)}")
            return {
                'has_conflict': True,
                'error': str(e),
                'message': 'Unable to verify seat availability'
            }
    
    @staticmethod
    def acquire_seat_lock(show_id, seat_ids, user_id, lock_duration_minutes=10):
        """Attempt to acquire a lock on selected seats"""
        from app.bookings.models import BookingSeat
        
        try:
            # Check existing locks
            existing_locks = db.session.query(BookingSeat).join(Booking).filter(
                BookingSeat.seat_id.in_(seat_ids),
                Booking.status == 'pending',
                Booking.booking_time >= datetime.utcnow() - timedelta(minutes=lock_duration_minutes)
            ).all()
            
            if existing_locks:
                return {
                    'locked': False,
                    'message': 'Some seats are currently locked by other users',
                    'existing_locks': [bs.seat_id for b in existing_locks for bs in b.booking_seats]
                }
            
            # Create temporary lock records
            # This would be implemented based on specific application requirements
            return {
                'locked': True,
                'message': f'Seat lock acquired for {lock_duration_minutes} minutes',
                'expires_at': datetime.utcnow() + timedelta(minutes=lock_duration_minutes)
            }
            
        except Exception as e:
            logging.error(f"Error acquiring seat lock: {str(e)}")
            return {
                'locked': False,
                'error': str(e),
                'message': 'Unable to acquire seat lock'
            }