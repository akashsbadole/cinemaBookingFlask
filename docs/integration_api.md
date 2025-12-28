# Cinema Management System - Integration API Documentation

This document describes the integration API endpoints that provide cross-module functionality for the Cinema Management System.

## Base URL
```
/api/integration
```

## Authentication
All endpoints require authentication with a valid user session. Admin-only endpoints are marked accordingly.

---

## Dashboard and Statistics

### Get Dashboard Statistics
**GET** `/dashboard`

Returns comprehensive dashboard statistics from all modules.

**Response:**
```json
{
  "success": true,
  "data": {
    "movies": {
      "active": 5,
      "total": 8,
      "inactive": 3
    },
    "screens": {
      "total": 3,
      "total_seats": 240
    },
    "shows": {
      "today": 12,
      "upcoming": 25,
      "total": 37
    },
    "bookings": {
      "today": 15,
      "pending": 3,
      "recent": [...]
    },
    "payments": {
      "today_revenue": 45000.00,
      "recent": [...]
    },
    "users": {
      "active": 4
    },
    "system_health": {
      "total_issues": 0,
      "high_severity": 0,
      "overall_status": "healthy"
    }
  }
}
```

---

## Data Integrity

### Check Data Integrity
**GET** `/integrity/check`

Runs comprehensive data integrity checks across all modules.

**Admin only:** Yes

**Response:**
```json
{
  "success": true,
  "data": {
    "timestamp": "2023-12-01T10:00:00Z",
    "checks": {
      "referential_integrity": {
        "status": "completed",
        "issues": []
      },
      "module_checks": {
        "movie_show_integrity": {
          "status": "healthy"
        },
        "screen_seat_integrity": {
          "status": "healthy"
        }
      }
    },
    "summary": {
      "total_issues": 0,
      "overall_status": "healthy"
    }
  }
}
```

### Fix Integrity Issues
**POST** `/integrity/fix`

Automatically fixes common integrity issues like orphaned records.

**Admin only:** Yes

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "completed",
    "fixes_applied": [
      {
        "type": "deleted_orphaned_booking_seats",
        "count": 5,
        "message": "Deleted 5 orphaned booking seat records"
      }
    ]
  }
}
```

---

## Cross-Module Data

### Get Cross-Module Data
**GET** `/data/<module_type>`

Retrieves integrated data across multiple modules.

**Parameters:**
- `module_type` (path): One of `movie_performance`, `screen_utilization`, `user_activity`, `revenue_analytics`
- `start_date` (query, optional): Filter start date (YYYY-MM-DD)
- `end_date` (query, optional): Filter end date (YYYY-MM-DD)
- `limit` (query, optional): Maximum number of results (default: 50)

**Example:**
```
GET /data/movie_performance?start_date=2023-11-01&end_date=2023-11-30
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "movie_id": 1,
      "title": "Action Movie",
      "genre": "Action",
      "language": "English",
      "total_shows": 15,
      "total_bookings": 120,
      "total_tickets_sold": 450,
      "total_revenue": 67500.00,
      "average_ticket_price": 150.00
    }
  ]
}
```

---

## Booking Workflow

### Get Available Movies
**GET** `/booking/movies`

Get movies with available shows for a specific date.

**Parameters:**
- `date` (query, optional): Date to check (YYYY-MM-DD, default: today)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "Action Movie",
      "genre": "Action",
      "language": "English",
      "duration": 120,
      "rating": "PG-13",
      "show_count": 3
    }
  ]
}
```

### Get Movie Shows
**GET** `/booking/movies/<movie_id>/shows`

Get available shows for a specific movie.

**Parameters:**
- `date` (query, optional): Date to check (YYYY-MM-DD, default: today)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "show_date": "2023-12-01",
      "show_time": "18:00",
      "end_time": "20:00",
      "base_price": 150.00,
      "screen_name": "Screen 1",
      "movie_title": "Action Movie",
      "total_seats": 80,
      "available_seats": 65,
      "occupancy_percentage": 18.75
    }
  ]
}
```

### Get Show Seat Layout
**GET** `/booking/shows/<show_id>/seats`

Get seat layout for a specific show with availability status.

**Response:**
```json
{
  "success": true,
  "data": {
    "show_id": 1,
    "movie_title": "Action Movie",
    "screen_name": "Screen 1",
    "show_date": "2023-12-01",
    "show_time": "18:00",
    "seat_layout": {
      "A": {
        "1": {
          "id": 1,
          "row": "A",
          "column": 1,
          "seat_number": "A1",
          "type": "normal",
          "base_price": 150.00,
          "final_price": 150.00,
          "status": "available"
        }
      }
    },
    "seat_types": {
      "normal": [...],
      "premium": [...],
      "vip": [...]
    },
    "total_seats": 80,
    "available_seats": 65,
    "occupied_seats": 15
  }
}
```

### Reserve Seats
**POST** `/booking/reserve`

Reserve seats for a show with temporary lock.

**Request Body:**
```json
{
  "show_id": 1,
  "seat_ids": [1, 2, 3],
  "lock_minutes": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Seats locked for 10 minutes",
  "locked_seats": [1, 2, 3],
  "expires_at": "2023-12-01T10:10:00Z"
}
```

### Create Booking
**POST** `/booking/create`

Create a booking with reserved seats.

**Request Body:**
```json
{
  "show_id": 1,
  "seat_ids": [1, 2, 3],
  "customer_info": {
    "customer_name": "John Doe",
    "customer_phone": "1234567890",
    "customer_email": "john@example.com",
    "payment_method": "cash"
  }
}
```

**Response:**
```json
{
  "success": true,
  "booking_id": 123,
  "reference_number": "BK231201001234",
  "total_amount": 450.00,
  "seats": ["A1", "A2", "A3"],
  "message": "Booking created successfully"
}
```

### Process Payment
**POST** `/booking/payment`

Process payment for a booking.

**Request Body:**
```json
{
  "booking_id": 123,
  "payment_info": {
    "mode": "card",
    "card_type": "visa",
    "card_last_4": "1234",
    "card_expiry_month": "12",
    "card_expiry_year": "2025"
  }
}
```

**Response:**
```json
{
  "success": true,
  "payment_id": 456,
  "booking_id": 123,
  "reference_number": "BK231201001234",
  "amount": 450.00,
  "status": "completed",
  "message": "Payment processed successfully"
}
```

### Complete Booking Workflow
**POST** `/booking/complete`

Complete the entire booking workflow in one transaction.

**Request Body:**
```json
{
  "movie_id": 1,
  "show_id": 1,
  "seat_ids": [1, 2, 3],
  "customer_info": {
    "customer_name": "John Doe",
    "customer_phone": "1234567890",
    "customer_email": "john@example.com",
    "payment_method": "card"
  },
  "payment_info": {
    "mode": "card",
    "card_type": "visa",
    "card_last_4": "1234"
  }
}
```

**Response:**
```json
{
  "success": true,
  "booking_id": 123,
  "reference_number": "BK231201001234",
  "payment_id": 456,
  "total_amount": 450.00,
  "seats": ["A1", "A2", "A3"],
  "message": "Booking completed successfully"
}
```

### Cancel Booking
**POST** `/booking/<booking_id>/cancel`

Cancel a booking and process refund if applicable.

**Request Body:**
```json
{
  "reason": "Customer request"
}
```

**Response:**
```json
{
  "success": true,
  "booking_id": 123,
  "reference_number": "BK231201001234",
  "refund_amount": 450.00,
  "message": "Booking cancelled successfully"
}
```

---

## Reporting Workflow

### Generate Report
**POST** `/reports/generate`

Generate comprehensive reports across all modules.

**Request Body:**
```json
{
  "start_date": "2023-11-01",
  "end_date": "2023-11-30",
  "report_type": "daily"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "report_type": "daily",
    "period": {
      "start_date": "2023-11-01",
      "end_date": "2023-11-30"
    },
    "daily_sales": [...],
    "payment_methods": [...],
    "occupancy_data": [...],
    "cashier_performance": [...]
  }
}
```

### Export Report
**POST** `/reports/export`

Export report data to CSV format.

**Request Body:**
```json
{
  "report_data": {...},
  "filename": "report_202311.csv"
}
```

**Response:**
```json
{
  "success": true,
  "filename": "report_202311.csv",
  "response": "<CSV file response>"
}
```

---

## Global Search

### Global Search
**GET** `/search`

Search across all modules with a simple query.

**Parameters:**
- `q` (query, required): Search query string
- `module` (query, optional): Module filter (all, movies, bookings, payments, shows, users)
- `limit` (query, optional): Maximum results (default: 20)
- `start_date` (query, optional): Date range start
- `end_date` (query, optional): Date range end

**Example:**
```
GET /search?q=John&module=bookings&limit=10
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "John",
    "filters": {...},
    "total_results": 5,
    "modules": {
      "bookings": [
        {
          "id": 123,
          "reference_number": "BK231201001234",
          "customer_name": "John Doe",
          "movie_title": "Action Movie",
          "total_amount": 450.00,
          "status": "confirmed",
          "type": "booking",
          "url": "/bookings/view/123"
        }
      ],
      "users": [...]
    }
  }
}
```

### Advanced Search
**POST** `/search/advanced`

Advanced search with multiple criteria.

**Request Body:**
```json
{
  "module_type": "bookings",
  "reference_number": "BK23",
  "customer_name": "John",
  "start_date": "2023-11-01",
  "end_date": "2023-11-30",
  "amount_min": 100,
  "amount_max": 1000
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "search_params": {...},
    "total_results": 3,
    "modules": {
      "bookings": [...]
    }
  }
}
```

### Search Suggestions
**GET** `/search/suggestions`

Get search suggestions for autocomplete.

**Parameters:**
- `q` (query, required): Partial query
- `module` (query, optional): Module filter
- `limit` (query, optional): Maximum suggestions (default: 10)

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "Act",
    "module_type": "all",
    "suggestions": {
      "movies": ["Action Movie", "Adventure Movie"],
      "customers": ["John Doe", "Jane Smith"],
      "users": ["admin", "cashier1"]
    }
  }
}
```

---

## Notifications

### Get User Notifications
**GET** `/notifications`

Get notifications for the current user.

**Parameters:**
- `unread_only` (query, optional): Get only unread notifications (true/false)
- `limit` (query, optional): Maximum notifications (default: 50)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "Booking Confirmed",
      "message": "Your booking BK231201001234 has been confirmed",
      "notification_type": "booking_confirmed",
      "is_read": false,
      "created_at": "2023-12-01T10:00:00Z",
      "action_url": "/bookings/view/123"
    }
  ]
}
```

### Get Unread Count
**GET** `/notifications/unread-count`

Get count of unread notifications.

**Response:**
```json
{
  "success": true,
  "data": {
    "count": 3
  }
}
```

### Mark Notification as Read
**POST** `/notifications/<notification_id>/read`

Mark a specific notification as read.

**Response:**
```json
{
  "success": true,
  "message": "Notification marked as read"
}
```

### Mark All as Read
**POST** `/notifications/read-all`

Mark all notifications as read for the current user.

**Response:**
```json
{
  "success": true,
  "data": {
    "count": 5
  }
}
```

### Create Notification
**POST** `/notifications/create`

Create a new notification (admin only).

**Admin only:** Yes

**Request Body:**
```json
{
  "title": "System Maintenance",
  "message": "System will be under maintenance from 2 AM to 4 AM",
  "notification_type": "system_alert",
  "channel": "in_app",
  "priority": "high",
  "user_id": 123,
  "expires_in_hours": 24
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 456,
    "title": "System Maintenance",
    "message": "System will be under maintenance from 2 AM to 4 AM",
    "notification_type": "system_alert",
    "priority": "high"
  }
}
```

---

## Cascade Operations

### Delete Movie
**DELETE** `/cascade/delete/movie/<movie_id>`

Safely delete a movie with cascade operations.

**Admin only:** Yes

**Response:**
```json
{
  "success": true,
  "message": "Movie deleted successfully",
  "deleted_shows": 3
}
```

### Delete Screen
**DELETE** `/cascade/delete/screen/<screen_id>`

Safely delete a screen with cascade operations.

**Admin only:** Yes

**Response:**
```json
{
  "success": true,
  "message": "Screen deleted successfully",
  "deleted_shows": 5,
  "deleted_seats": 80
}
```

### Delete User
**DELETE** `/cascade/delete/user/<user_id>`

Safely delete a user with cascade operations.

**Admin only:** Yes

**Response:**
```json
{
  "success": true,
  "message": "User deactivated successfully",
  "cancelled_bookings": 2
}
```

---

## System Health

### Get System Health
**GET** `/health`

Get overall system health status.

**Response:**
```json
{
  "success": true,
  "data": {
    "database": "connected",
    "integrity": {
      "total_issues": 0,
      "overall_status": "healthy"
    },
    "timestamp": "2023-12-01T10:00:00Z"
  }
}
```

---

## Error Responses

All endpoints return error responses in the following format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

---

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- Search endpoints: 100 requests per minute
- Booking endpoints: 50 requests per minute
- Report endpoints: 20 requests per minute
- Other endpoints: 200 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1638360000
```

---

## WebSocket Support

Real-time notifications are available via WebSocket:

**Connection URL:**
```
ws://localhost:5000/ws/notifications
```

**Message Format:**
```json
{
  "type": "notification",
  "data": {
    "id": 123,
    "title": "New Booking",
    "message": "Booking BK231201001234 has been created"
  }
}
```

---

## SDK Examples

### JavaScript/Node.js

```javascript
// Initialize client
const client = new CinemaIntegrationClient({
  baseURL: 'http://localhost:5000/api/integration',
  apiKey: 'your-api-key'
});

// Get dashboard statistics
const dashboard = await client.getDashboard();
console.log(dashboard.data.movies.active);

// Complete booking workflow
const booking = await client.completeBooking({
  movie_id: 1,
  show_id: 1,
  seat_ids: [1, 2, 3],
  customer_info: {
    customer_name: 'John Doe',
    customer_email: 'john@example.com'
  },
  payment_info: {
    mode: 'card',
    card_type: 'visa'
  }
});
```

### Python

```python
from cinema_integration import CinemaClient

# Initialize client
client = CinemaClient(
    base_url='http://localhost:5000/api/integration',
    api_key='your-api-key'
)

# Get dashboard statistics
dashboard = client.get_dashboard()
print(f"Active movies: {dashboard['data']['movies']['active']}")

# Search bookings
results = client.advanced_search(
    module_type='bookings',
    customer_name='John',
    start_date='2023-11-01'
)
```

---

## Changelog

### v2.1.0 (2023-12-01)
- Added integration API endpoints
- Implemented global search functionality
- Added unified notifications system
- Enhanced dashboard with real-time updates
- Added comprehensive reporting workflow

### v2.0.0 (2023-11-01)
- Initial API release
- Basic CRUD operations for all modules
- Authentication and authorization