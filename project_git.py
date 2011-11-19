# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from osv import fields
from git import *
from datetime import datetime

def read_repo_reflog(repo):
	head = repo.head
	master = head.reference
	log = master.log()
	return log

class project_task_git_repo(osv.osv):
	_name = "project.task.git.repo"

	_columns = {
		'name': fields.char("Name", size = 128),
		'path': fields.char("Path", size = 255),
		'actual_revision': fields.char("Actual revision", size = 40),	
	}


project_task_git_repo()

class project_task(osv.osv):
	_name = "project.task"
	_inherit = "project.task"

	_columns = {
		'repo_id': fields.many2one('project.task.git.repo', 'Git Repository')
	}

	def create_task_work_from_commit(self, cr, uid, commit, task_id):
		user_obj = self.pool.get('res.users')

		commit_date = datetime.fromtimestamp(commit.authored_date)

		task_values = {'name': commit.message, 'date': commit_date,
			      'task_id': task_id}
		
		#Find User who made the commit
		addr_ids = self.pool.get('res.partner.address').search(cr, uid,
			['|',('email','=',commit.author.email),
			('name','=',commit.author.name)])

		for addr_id in addr_ids:
			commit_user_ids = user_obj.search(cr, uid, 
				[('address_id','=',addr_id)])

			if commit_user_ids:
				task_values['user_id'] = commit_user_ids[0]
			
		task_work = self.pool.get('project.task.work').create(cr, 
			uid, task_values)

	def read_repo_revisions(self, cr, uid, ids, *args):
		actual_revision = False

		for obj in self.browse(cr, uid, ids, *args):
			repo_obj = obj.repo_id
			
			if not repo_obj:
				continue

			try:
				repo = Repo(repo_obj.path)
			except InvalidGitRepositoryError:
				repo = False
			
			if not repo:
				continue
			
			if not repo_obj.actual_revision:
				reflog = read_repo_reflog(repo)

				for ref in reflog:
					commit = repo.rev_parse(ref.newhexsha)
					task_work = self.create_task_work_from_commit(cr, uid,
						commit, obj.id)
				
				actual_revision = reflog[-1].newhexsha
			 	
			else:
				reflog = read_repo_reflog(repo)

				actual_ref = [ref for ref in reflog \
					if ref.oldhexsha == repo_obj.actual_revision]
				
				if len(actual_ref):
				 	ref_index = reflog.index(actual_ref[0])					

					new_refs = reflog[ref_index:]
									
					for ref in new_refs:
						commit = repo.rev_parse(ref.newhexsha)
						task_work = self.create_task_work_from_commit(cr, uid,
							 commit, obj.id)

					if len(new_refs):
						actual_revision = new_refs[-1].newhexsha

		if actual_revision:
			self.pool.get('project.task.git.repo').write(cr, uid,
				 		repo_obj.id, {'actual_revision': actual_revision})
						
		return True

project_task()