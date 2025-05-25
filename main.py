from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
import sqlite3
import json
from pathlib import Path
import fitz  # PyMuPDF for PDF handling
from datetime import datetime
from ui import Ui_MainWindow

class ArticleDatabase:
    def __init__(self, db_path="articles.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Articles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                group_id INTEGER,
                pages INTEGER DEFAULT 0,
                is_read BOOLEAN DEFAULT FALSE,
                is_indexed BOOLEAN DEFAULT FALSE,
                date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_read DATETIME,
                file_size INTEGER,
                keywords TEXT,
                notes TEXT,
                FOREIGN KEY (group_id) REFERENCES groups (id)
            )
        ''')
        
        # Groups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT DEFAULT '#3498db',
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Article content index table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS article_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                page_number INTEGER,
                content TEXT,
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_article(self, title, file_path, group_id=None):
        """Add a new article to the database"""
        # Check if article with same file path already exists
        if self.article_exists(file_path):
            return None  # Article already exists
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get file info
        file_size = os.path.getsize(file_path)
        pages = self.get_pdf_page_count(file_path)
        
        try:
            cursor.execute('''
                INSERT INTO articles (title, file_path, group_id, pages, file_size)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, file_path, group_id, pages, file_size))
            
            article_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return article_id
        except sqlite3.IntegrityError:
            # File path already exists due to UNIQUE constraint
            conn.close()
            return None
    
    def article_exists(self, file_path):
        """Check if an article with the given file path already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles WHERE file_path = ?", (file_path,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        return exists
    
    def get_pdf_page_count(self, file_path):
        """Get the number of pages in a PDF file"""
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except:
            return 0
    
    def get_statistics(self):
        """Get article statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        stats['total_articles'] = cursor.fetchone()[0]
        
        # Read articles
        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = TRUE")
        stats['read_articles'] = cursor.fetchone()[0]
        
        # Total pages
        cursor.execute("SELECT SUM(pages) FROM articles")
        total_pages = cursor.fetchone()[0]
        stats['total_pages'] = total_pages if total_pages else 0
        
        # Pages read (sum of pages from read articles)
        cursor.execute("SELECT SUM(pages) FROM articles WHERE is_read = TRUE")
        pages_read = cursor.fetchone()[0]
        stats['pages_read'] = pages_read if pages_read else 0
        
        # Indexed articles
        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_indexed = TRUE")
        stats['indexed_articles'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def get_all_articles(self, group_id=None, search_query=None):
        """Get all articles with optional filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM articles WHERE 1=1"
        params = []
        
        if group_id:
            query += " AND group_id = ?"
            params.append(group_id)
        
        if search_query:
            query += " AND (title LIKE ? OR keywords LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        
        cursor.execute(query, params)
        articles = cursor.fetchall()
        conn.close()
        return articles
    
    def get_all_groups(self):
        """Get all groups"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups")
        groups = cursor.fetchall()
        conn.close()
        return groups
    
    def add_group(self, name, description="", color="#3498db"):
        """Add a new group"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO groups (name, description, color)
            VALUES (?, ?, ?)
        ''', (name, description, color))
        group_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return group_id
    
    def mark_as_read(self, article_id):
        """Mark an article as read"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE articles 
            SET is_read = TRUE, date_read = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (article_id,))
        conn.commit()
        conn.close()
    
    def mark_as_unread(self, article_id):
        """Mark an article as unread"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE articles 
            SET is_read = FALSE, date_read = NULL 
            WHERE id = ?
        ''', (article_id,))
        conn.commit()
        conn.close()
    
    def get_article_read_status(self, article_id):
        """Get the read status of an article"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT is_read FROM articles WHERE id = ?", (article_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else False
    
    def index_article_content(self, article_id, file_path):
        """Index article content for search"""
        try:
            doc = fitz.open(file_path)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                
                cursor.execute('''
                    INSERT INTO article_index (article_id, page_number, content)
                    VALUES (?, ?, ?)
                ''', (article_id, page_num + 1, text))
            
            # Mark article as indexed
            cursor.execute('''
                UPDATE articles SET is_indexed = TRUE WHERE id = ?
            ''', (article_id,))
            
            conn.commit()
            conn.close()
            doc.close()
            return True
        except Exception as e:
            print(f"Error indexing article: {e}")
            return False

class PDFViewer:
    def __init__(self):
        self.current_document = None
        self.current_page = 0
    
    def load_pdf(self, file_path):
        """Load a PDF file for viewing"""
        try:
            if self.current_document:
                self.current_document.close()
            
            self.current_document = fitz.open(file_path)
            self.current_page = 0
            return True
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return False
    
    def get_page_pixmap(self, page_num=None, zoom=1.0):
        """Get a pixmap of the specified page"""
        if not self.current_document:
            return None
        
        if page_num is None:
            page_num = self.current_page
        
        if page_num >= len(self.current_document):
            return None
        
        try:
            page = self.current_document.load_page(page_num)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            return pix
        except Exception as e:
            print(f"Error getting page pixmap: {e}")
            return None
    
    def get_page_count(self):
        """Get the total number of pages"""
        if self.current_document:
            return len(self.current_document)
        return 0
    
    def next_page(self):
        """Go to next page"""
        if self.current_document and self.current_page < len(self.current_document) - 1:
            self.current_page += 1
            return True
        return False
    
    def previous_page(self):
        """Go to previous page"""
        if self.current_document and self.current_page > 0:
            self.current_page -= 1
            return True
        return False

class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Initialize database and PDF viewer
        self.db = ArticleDatabase()
        self.pdf_viewer = PDFViewer()
        
        # Current selections
        self.current_article_id = None
        self.current_group_id = None
        
        # Initialize UI components (will be implemented in UI updates)
        self.setup_connections()
        self.refresh_statistics()
        self.refresh_groups()
        self.refresh_articles()
        
        # Initialize zoom slider
        self.ui.zoomhorizontalSlider.setMinimum(25)
        self.ui.zoomhorizontalSlider.setMaximum(200)
        self.ui.zoomhorizontalSlider.setValue(100)
        self.current_zoom = 1.0
        
        # Setup context menus
        self.setup_context_menus()
    
    def setup_connections(self):
        """Setup signal connections for UI elements"""
        # Search and Add (Articles Section)
        self.ui.searchpushButton.clicked.connect(self.on_search_clicked)
        self.ui.addFilepushButton.clicked.connect(self.on_add_file_clicked)
        self.ui.addFolderpushButton.clicked.connect(self.on_add_folder_clicked)
        self.ui.searchlineEdit.returnPressed.connect(self.on_search_clicked)
        
        # Groups Management
        self.ui.newGrouppushButton.clicked.connect(self.on_new_group_clicked)
        self.ui.editpushButton.clicked.connect(self.on_edit_group_clicked)
        self.ui.deletepushButton.clicked.connect(self.on_delete_group_clicked)
        self.ui.groupslistWidget.itemClicked.connect(self.on_group_selected)
        
        # Articles List
        self.ui.articleslistWidget.itemClicked.connect(self.on_article_selected)
        self.ui.articleslistWidget.itemDoubleClicked.connect(self.on_article_double_clicked)
        self.ui.sortcomboBox.currentTextChanged.connect(self.on_sort_changed)
        self.ui.showOnlyReadcheckBox.toggled.connect(self.on_show_read_toggled)
        self.ui.showOnlyUnreadcheckBox.toggled.connect(self.on_show_unread_toggled)
        
        # Preview Navigation
        self.ui.previouspushButton.clicked.connect(self.on_previous_page)
        self.ui.nextpushButton.clicked.connect(self.on_next_page)
        self.ui.pagespinBox.valueChanged.connect(self.on_page_changed)
        
        # Preview Controls
        self.ui.zoomOutpushButton.clicked.connect(self.on_zoom_out)
        self.ui.zoomInpushButton.clicked.connect(self.on_zoom_in)
        self.ui.fitWidthpushButton.clicked.connect(self.on_fit_width)
        self.ui.zoomhorizontalSlider.valueChanged.connect(self.on_zoom_changed)
        self.ui.markAsReadpushButton.clicked.connect(self.mark_current_as_read)
        self.ui.openExternalpushButton.clicked.connect(self.on_open_external)
    
    def setup_context_menus(self):
        """Setup context menus for UI elements"""
        # Articles list context menu
        self.ui.articleslistWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.articleslistWidget.customContextMenuRequested.connect(self.show_article_context_menu)
    
    def refresh_statistics(self):
        """Update statistics display"""
        stats = self.db.get_statistics()
        
        # Update statistics labels
        self.ui.totalArticleslabel.setText(str(stats['total_articles']))
        self.ui.articlesReadlabel.setText(str(stats['read_articles']))
        self.ui.totalPageslabel.setText(str(stats['total_pages']))
        self.ui.indexedArticleslabel.setText(str(stats['indexed_articles']))
        self.ui.pagesReadlabel.setText(str(stats['pages_read']))
        
        # Update progress bars
        if stats['total_articles'] > 0:
            read_percentage = int((stats['read_articles'] / stats['total_articles']) * 100)
            index_percentage = int((stats['indexed_articles'] / stats['total_articles']) * 100)
        else:
            read_percentage = 0
            index_percentage = 0
            
        self.ui.readingprogressBar.setValue(read_percentage)
        self.ui.indexingprogressBar.setValue(index_percentage)
    
    def refresh_groups(self):
        """Update groups display"""
        groups = self.db.get_all_groups()
        
        # Clear current groups
        self.ui.groupslistWidget.clear()
        
        # Add "All Groups" option
        all_groups_item = QtWidgets.QListWidgetItem("📚 All Groups")
        all_groups_item.setData(QtCore.Qt.UserRole, None)  # None indicates all groups
        self.ui.groupslistWidget.addItem(all_groups_item)
        
        # Add each group
        for group in groups:
            group_id, name, description, color, date_created = group
            display_text = f"📁 {name}"
            if description:
                display_text += f" - {description}"
                
            group_item = QtWidgets.QListWidgetItem(display_text)
            group_item.setData(QtCore.Qt.UserRole, group_id)
            
            # Set group color if available
            if color:
                try:
                    group_item.setForeground(QtGui.QColor(color))
                except:
                    pass
                    
            self.ui.groupslistWidget.addItem(group_item)
    
    def refresh_articles(self):
        """Update articles list"""
        # Get search query if any
        search_query = self.ui.searchlineEdit.text().strip()
        if not search_query:
            search_query = None
            
        # Check if showing only read articles
        show_only_read = self.ui.showOnlyReadcheckBox.isChecked()
        show_only_unread = self.ui.showOnlyUnreadcheckBox.isChecked()
        
        articles = self.db.get_all_articles(
            group_id=self.current_group_id,
            search_query=search_query
        )
        
        # Filter by read status if needed
        if show_only_read:
            articles = [article for article in articles if article[5]]  # is_read column
        elif show_only_unread:
            articles = [article for article in articles if not article[5]]  # not is_read column
        
        # Clear current articles
        self.ui.articleslistWidget.clear()
        
        # Sort articles based on sort combo box
        sort_option = self.ui.sortcomboBox.currentText()
        if sort_option == "Title":
            articles.sort(key=lambda x: x[1])  # title column
        elif sort_option == "Pages":
            articles.sort(key=lambda x: x[4], reverse=True)  # pages column
        elif sort_option == "Read Status":
            articles.sort(key=lambda x: x[5], reverse=True)  # is_read column
        else:  # Date Added (default)
            articles.sort(key=lambda x: x[7], reverse=True)  # date_added column
        
        # Add each article
        for article in articles:
            article_id, title, file_path, group_id, pages, is_read, is_indexed, date_added, date_read, file_size, keywords, notes = article
            
            # Create display text with status indicators
            read_status = "✓" if is_read else "○"
            indexed_status = "🔍" if is_indexed else "○"
            
            # Format file size
            if file_size:
                if file_size > 1024 * 1024:
                    size_str = f"{file_size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = "Unknown"
            
            display_text = f"{read_status} {indexed_status} {title}"
            detail_text = f"📄 {pages} pages • {size_str} • {os.path.basename(file_path)}"
            
            # Create list item
            article_item = QtWidgets.QListWidgetItem()
            article_item.setText(f"{display_text}\n{detail_text}")
            article_item.setData(QtCore.Qt.UserRole, article_id)
            
            # Color coding based on status
            if is_read:
                article_item.setForeground(QtGui.QColor("#2ecc71"))  # Green for read
            elif is_indexed:
                article_item.setForeground(QtGui.QColor("#3498db"))  # Blue for indexed
            else:
                article_item.setForeground(QtGui.QColor("#e74c3c"))  # Red for unprocessed
                
            self.ui.articleslistWidget.addItem(article_item)
    
    def add_article_from_file(self, file_path):
        """Add an article from a file path"""
        if not os.path.exists(file_path):
            return False
        
        title = os.path.splitext(os.path.basename(file_path))[0]
        article_id = self.db.add_article(title, file_path, self.current_group_id)
        
        # Check if article was actually added (not a duplicate)
        if article_id is None:
            return False  # Article already exists or failed to add
        
        # Auto-index the article content
        self.db.index_article_content(article_id, file_path)
        
        self.refresh_statistics()
        self.refresh_articles()
        return True
    
    def add_folder_articles(self, folder_path):
        """Add all PDF files from a folder (not including subfolders)"""
        pdf_files = []
        skipped_files = []
        
        # Use glob instead of rglob to only get files from the immediate folder
        for file_path in Path(folder_path).glob("*.pdf"):
            if self.add_article_from_file(str(file_path)):
                pdf_files.append(str(file_path))
            else:
                skipped_files.append(str(file_path))
        
        return pdf_files, skipped_files
    
    def search_articles(self, query):
        """Search articles by title or content"""
        articles = self.db.get_all_articles(search_query=query)
        # Update articles display with search results
        return articles
    
    def filter_by_group(self, group_id):
        """Filter articles by group"""
        self.current_group_id = group_id
        self.refresh_articles()
    
    def preview_article(self, article_id):
        """Preview an article in the PDF viewer"""
        # Get article info from database
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, is_read FROM articles WHERE id = ?", (article_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            file_path, is_read = result
            if self.pdf_viewer.load_pdf(file_path):
                self.current_article_id = article_id
                
                # Update mark as read button text based on current status
                if is_read:
                    self.ui.markAsReadpushButton.setText("↩ Mark as Unread")
                else:
                    self.ui.markAsReadpushButton.setText("✓ Mark as Read")
                
                self.update_pdf_preview()
                return True
        return False
    
    def update_pdf_preview(self):
        """Update the PDF preview display"""
        pixmap = self.pdf_viewer.get_page_pixmap(zoom=self.current_zoom)
        if pixmap:
            # Convert PyMuPDF pixmap to QPixmap
            img_data = pixmap.tobytes("ppm")
            qimg = QtGui.QImage.fromData(img_data)
            qpixmap = QtGui.QPixmap.fromImage(qimg)
            
            # Update the preview label
            self.ui.previewlabel.setPixmap(qpixmap)
            self.ui.previewlabel.setScaledContents(False)
            self.ui.previewlabel.setAlignment(QtCore.Qt.AlignCenter)
            
            # Update page info
            current_page = self.pdf_viewer.current_page + 1
            total_pages = self.pdf_viewer.get_page_count()
            self.ui.pageNumlabel.setText(f"Page {current_page} of {total_pages}")
            
            # Update page spin box
            self.ui.pagespinBox.blockSignals(True)
            self.ui.pagespinBox.setMinimum(1)
            self.ui.pagespinBox.setMaximum(total_pages)
            self.ui.pagespinBox.setValue(current_page)
            self.ui.pagespinBox.blockSignals(False)
            
            # Update zoom label
            zoom_percentage = int(self.current_zoom * 100)
            self.ui.zoomlabel.setText(f"{zoom_percentage}%")
            
            # Update zoom slider
            self.ui.zoomhorizontalSlider.blockSignals(True)
            self.ui.zoomhorizontalSlider.setValue(zoom_percentage)
            self.ui.zoomhorizontalSlider.blockSignals(False)
            
            # Adjust scroll area to fit content
            self.ui.previewlabel.resize(qpixmap.size())
        else:
            # Clear preview if no pixmap
            self.ui.previewlabel.clear()
            self.ui.previewlabel.setText("No preview available")
            self.ui.pageNumlabel.setText("Page 0 of 0")
    
    def mark_current_as_read(self):
        """Toggle read status of current article"""
        if self.current_article_id:
            # Get current read status
            is_currently_read = self.db.get_article_read_status(self.current_article_id)
            
            if is_currently_read:
                # Mark as unread
                self.db.mark_as_unread(self.current_article_id)
                self.ui.markAsReadpushButton.setText("✓ Mark as Read")
            else:
                # Mark as read
                self.db.mark_as_read(self.current_article_id)
                self.ui.markAsReadpushButton.setText("↩ Mark as Unread")
            
            self.refresh_statistics()
            self.refresh_articles()
    
    def create_new_group(self, name, description="", color="#3498db"):
        """Create a new group"""
        group_id = self.db.add_group(name, description, color)
        self.refresh_groups()
        return group_id
    
    # UI Event Handlers
    def on_search_clicked(self):
        """Handle search button click"""
        self.refresh_articles()
    
    def on_add_file_clicked(self):
        """Handle add file button click"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select PDF File", "", "PDF Files (*.pdf)"
        )
        if file_path:
            if self.add_article_from_file(file_path):
                QtWidgets.QMessageBox.information(
                    self, "File Added", 
                    f"Successfully added: {os.path.basename(file_path)}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Duplicate File", 
                    f"File already exists in library: {os.path.basename(file_path)}"
                )
    
    def on_add_folder_clicked(self):
        """Handle add folder button click"""
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Folder Containing PDFs"
        )
        if folder_path:
            pdf_files, skipped_files = self.add_folder_articles(folder_path)
            QtWidgets.QMessageBox.information(
                self, "Import Complete", 
                f"Imported {len(pdf_files)} PDF files from folder. Skipped {len(skipped_files)} duplicates."
            )
    
    def on_new_group_clicked(self):
        """Handle new group button click"""
        dialog = GroupDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            name, description, color = dialog.get_group_data()
            self.create_new_group(name, description, color)
    
    def on_edit_group_clicked(self):
        """Handle edit group button click"""
        current_item = self.ui.groupslistWidget.currentItem()
        if current_item:
            group_id = current_item.data(QtCore.Qt.UserRole)
            if group_id:  # Don't edit "All Groups"
                # Get current group data
                conn = sqlite3.connect(self.db.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name, description, color FROM groups WHERE id = ?", (group_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    name, description, color = result
                    dialog = GroupDialog(self, name, description, color)
                    if dialog.exec_() == QtWidgets.QDialog.Accepted:
                        new_name, new_description, new_color = dialog.get_group_data()
                        # Update group in database
                        conn = sqlite3.connect(self.db.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE groups SET name = ?, description = ?, color = ?
                            WHERE id = ?
                        ''', (new_name, new_description, new_color, group_id))
                        conn.commit()
                        conn.close()
                        self.refresh_groups()
    
    def on_delete_group_clicked(self):
        """Handle delete group button click"""
        current_item = self.ui.groupslistWidget.currentItem()
        if current_item:
            group_id = current_item.data(QtCore.Qt.UserRole)
            if group_id:  # Don't delete "All Groups"
                reply = QtWidgets.QMessageBox.question(
                    self, "Delete Group", 
                    "Are you sure you want to delete this group?\nArticles will not be deleted.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    conn = sqlite3.connect(self.db.db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                    # Remove group assignment from articles
                    cursor.execute("UPDATE articles SET group_id = NULL WHERE group_id = ?", (group_id,))
                    conn.commit()
                    conn.close()
                    self.refresh_groups()
                    self.refresh_articles()
    
    def on_group_selected(self, item):
        """Handle group selection"""
        group_id = item.data(QtCore.Qt.UserRole)
        self.current_group_id = group_id
        self.refresh_articles()
    
    def on_article_selected(self, item):
        """Handle article selection"""
        article_id = item.data(QtCore.Qt.UserRole)
        if article_id:
            self.preview_article(article_id)
    
    def on_article_double_clicked(self, item):
        """Handle article double click - open externally"""
        article_id = item.data(QtCore.Qt.UserRole)
        if article_id:
            self.on_open_external()
    
    def on_sort_changed(self):
        """Handle sort option change"""
        self.refresh_articles()
    
    def on_show_read_toggled(self):
        """Handle show only read toggle"""
        if self.ui.showOnlyReadcheckBox.isChecked():
            # Uncheck the unread checkbox to make them mutually exclusive
            self.ui.showOnlyUnreadcheckBox.blockSignals(True)
            self.ui.showOnlyUnreadcheckBox.setChecked(False)
            self.ui.showOnlyUnreadcheckBox.blockSignals(False)
        self.refresh_articles()
    
    def on_show_unread_toggled(self):
        """Handle show only unread toggle"""
        if self.ui.showOnlyUnreadcheckBox.isChecked():
            # Uncheck the read checkbox to make them mutually exclusive
            self.ui.showOnlyReadcheckBox.blockSignals(True)
            self.ui.showOnlyReadcheckBox.setChecked(False)
            self.ui.showOnlyReadcheckBox.blockSignals(False)
        self.refresh_articles()
    
    def on_previous_page(self):
        """Handle previous page button"""
        if self.pdf_viewer.previous_page():
            self.update_pdf_preview()
    
    def on_next_page(self):
        """Handle next page button"""
        if self.pdf_viewer.next_page():
            self.update_pdf_preview()
    
    def on_page_changed(self, value):
        """Handle page spin box change"""
        page_num = value - 1  # Convert to 0-based
        if self.pdf_viewer.current_document and 0 <= page_num < self.pdf_viewer.get_page_count():
            self.pdf_viewer.current_page = page_num
            self.update_pdf_preview()
    
    def on_zoom_out(self):
        """Handle zoom out button"""
        self.current_zoom = max(0.25, self.current_zoom - 0.25)
        self.update_pdf_preview()
    
    def on_zoom_in(self):
        """Handle zoom in button"""
        self.current_zoom = min(2.0, self.current_zoom + 0.25)
        self.update_pdf_preview()
    
    def on_fit_width(self):
        """Handle fit width button"""
        if self.pdf_viewer.current_document:
            # Calculate zoom to fit width
            scroll_area_width = self.ui.previewscrollArea.viewport().width()
            pixmap = self.pdf_viewer.get_page_pixmap(zoom=1.0)
            if pixmap:
                page_width = pixmap.width
                self.current_zoom = (scroll_area_width - 20) / page_width  # 20px margin
                self.current_zoom = max(0.25, min(2.0, self.current_zoom))
                self.update_pdf_preview()
    
    def on_zoom_changed(self, value):
        """Handle zoom slider change"""
        self.current_zoom = value / 100.0
        self.update_pdf_preview()
    
    def on_open_external(self):
        """Handle open external button"""
        if self.current_article_id:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM articles WHERE id = ?", (self.current_article_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                file_path = result[0]
                try:
                    os.startfile(file_path)  # Windows
                except AttributeError:
                    try:
                        os.system(f'open "{file_path}"')  # macOS
                    except:
                        os.system(f'xdg-open "{file_path}"')  # Linux

    def show_article_context_menu(self, position):
        """Show context menu for articles list"""
        item = self.ui.articleslistWidget.itemAt(position)
        if item:
            article_id = item.data(QtCore.Qt.UserRole)
            if article_id:
                # Get current read status
                is_read = self.db.get_article_read_status(article_id)
                
                menu = QtWidgets.QMenu()
                
                # Toggle read status action
                if is_read:
                    toggle_action = menu.addAction("↩ Mark as Unread")
                else:
                    toggle_action = menu.addAction("✓ Mark as Read")
                
                menu.addSeparator()
                
                # Other actions
                preview_action = menu.addAction("👁 Open Preview")
                external_action = menu.addAction("📖 Open External")
                
                menu.addSeparator()
                
                # Group actions
                group_menu = menu.addMenu("📁 Move to Group")
                groups = self.db.get_all_groups()
                
                # Add "No Group" option
                no_group_action = group_menu.addAction("📂 No Group")
                group_menu.addSeparator()
                
                # Add existing groups
                group_actions = {}
                for group in groups:
                    group_id, name, description, color, date_created = group
                    action = group_menu.addAction(f"📁 {name}")
                    group_actions[action] = group_id
                
                menu.addSeparator()
                remove_action = menu.addAction("🗑️ Remove from Library")
                
                # Execute menu
                action = menu.exec_(self.ui.articleslistWidget.mapToGlobal(position))
                
                if action == toggle_action:
                    self.toggle_article_read_status(article_id)
                elif action == preview_action:
                    self.preview_article(article_id)
                elif action == external_action:
                    self.current_article_id = article_id
                    self.on_open_external()
                elif action == no_group_action:
                    self.move_article_to_group(article_id, None)
                elif action in group_actions:
                    self.move_article_to_group(article_id, group_actions[action])
                elif action == remove_action:
                    self.remove_article(article_id)
    
    def toggle_article_read_status(self, article_id):
        """Toggle read status of specified article"""
        is_currently_read = self.db.get_article_read_status(article_id)
        
        if is_currently_read:
            self.db.mark_as_unread(article_id)
        else:
            self.db.mark_as_read(article_id)
        
        # Update button text if this is the currently viewed article
        if self.current_article_id == article_id:
            is_read = self.db.get_article_read_status(article_id)
            if is_read:
                self.ui.markAsReadpushButton.setText("↩ Mark as Unread")
            else:
                self.ui.markAsReadpushButton.setText("✓ Mark as Read")
        
        self.refresh_statistics()
        self.refresh_articles()
    
    def move_article_to_group(self, article_id, group_id):
        """Move article to specified group"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE articles SET group_id = ? WHERE id = ?", (group_id, article_id))
        conn.commit()
        conn.close()
        self.refresh_articles()
    
    def remove_article(self, article_id):
        """Remove article from library"""
        reply = QtWidgets.QMessageBox.question(
            self, "Remove Article", 
            "Are you sure you want to remove this article from the library?\nThe file will not be deleted from disk.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            # Remove from article_index first (foreign key constraint)
            cursor.execute("DELETE FROM article_index WHERE article_id = ?", (article_id,))
            # Remove from articles
            cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            conn.commit()
            conn.close()
            
            # Clear preview if this was the current article
            if self.current_article_id == article_id:
                self.current_article_id = None
                self.ui.previewlabel.clear()
                self.ui.previewlabel.setText("No article selected")
                self.ui.pageNumlabel.setText("Page 0 of 0")
                self.ui.markAsReadpushButton.setText("✓ Mark as Read")
            
            self.refresh_statistics()
            self.refresh_articles()

class GroupDialog(QtWidgets.QDialog):
    """Dialog for creating/editing groups"""
    def __init__(self, parent=None, name="", description="", color="#3498db"):
        super().__init__(parent)
        self.setWindowTitle("Group Management")
        self.setModal(True)
        self.resize(400, 300)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Name input
        layout.addWidget(QtWidgets.QLabel("Group Name:"))
        self.name_edit = QtWidgets.QLineEdit(name)
        layout.addWidget(self.name_edit)
        
        # Description input
        layout.addWidget(QtWidgets.QLabel("Description (optional):"))
        self.description_edit = QtWidgets.QTextEdit(description)
        self.description_edit.setMaximumHeight(100)
        layout.addWidget(self.description_edit)
        
        # Color input
        color_layout = QtWidgets.QHBoxLayout()
        color_layout.addWidget(QtWidgets.QLabel("Color:"))
        self.color_button = QtWidgets.QPushButton()
        self.color_button.setFixedSize(50, 30)
        self.current_color = color
        self.update_color_button()
        self.color_button.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("OK")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # Focus on name field
        self.name_edit.setFocus()
    
    def update_color_button(self):
        """Update the color button appearance"""
        self.color_button.setStyleSheet(f"background-color: {self.current_color};")
    
    def choose_color(self):
        """Open color picker dialog"""
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self.update_color_button()
    
    def get_group_data(self):
        """Get the group data from the dialog"""
        return (
            self.name_edit.text().strip(),
            self.description_edit.toPlainText().strip(),
            self.current_color
        )
    
    def accept(self):
        """Override accept to validate input"""
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Group name cannot be empty.")
            return
        super().accept()

def App():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    win = Main()
    win.showMaximized()
    sys.exit(app.exec_())

App()