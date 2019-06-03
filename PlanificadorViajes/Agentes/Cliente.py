# -*- coding: utf-8 -*-
"""
filename: UserPersonalAgent
Agent que implementa la interacció amb l'usuari
@author: ecsdi
"""
import random

import sys

import urllib.parse

import argparse
import socket
from multiprocessing import Process
from flask import Flask, render_template, request
from rdflib import Graph, Namespace, RDF, URIRef, Literal, XSD

from PlanificadorViajes.AgentUtil.ACLMessages import Agent,get_agent_info, build_message, send_message
from PlanificadorViajes.AgentUtil.FlaskServer import shutdown_server
from PlanificadorViajes.AgentUtil.Logging import config_logger
from PlanificadorViajes.AgentUtil.OntologyNamespaces import ACL
from PlanificadorViajes.AgentUtil.OntologyNamespaces import Ontologia

__author__ = 'ecsdi'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default=socket.gethostname(), help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")
parser.add_argument('--host', default=socket.gethostname(), help="Host del agente")

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9001
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = socket.gethostname()

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost

# Flask stuff
app = Flask(__name__, template_folder='../templates')

# Configuration constants and variables
agn = Namespace("http://www.agentes.org/#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
UserClient = Agent('Cliente',
                          agn.UserClient,
                          'http://%s:%d/comm' % (hostname, port),
                          'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

#identificacion agentes

# Global dsgraph triplestore
dsgraph = Graph()

# Productos enconctrados
product_list = []
product_list2 = []
product_list3 = []
product_list4 = []

# Compras enconctrados
compras = []


def get_count():
    global mss_cnt
    if not mss_cnt:
        mss_cnt = 0
    mss_cnt += 1
    return mss_cnt


@app.route("/", methods=['GET', 'POST'])
def planificar():
    if request.method == 'GET':
        return render_template('planificar.html')
    elif request.method == 'POST':
        
        Planificador = get_agent_info(agn.AgentePlanificador, DirectoryAgent, UserClient, get_count())

        logger.info("Agente Planificador encontrado")

        gr = Graph()

        contentResult = Ontologia['Peticion_Buscar' + str(get_count())]
        EnviarFormularioPlanificar = Ontologia.EnviarFormularioPlanificar
        gr.add((contentResult, RDF.type, EnviarFormularioPlanificar))
        gr.add((EnviarFormularioPlanificar, Ontologia.tematica, Literal(request.form['tematica'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.ciudad_destino, Literal(request.form['ciudad_destino'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.ciudad_origen, Literal(request.form['ciudad_origen'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.precio_max, Literal(request.form['precio_max'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.precio_min, Literal(request.form['precio_min'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.beginning, Literal(request.form['beginning'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.end, Literal(request.form['end'])))
        gr.add((EnviarFormularioPlanificar, Ontologia.correo, Literal(request.form['correo'])))

        fechaIda = request.form['beginning']
        fechaVuelta = request.form['end']

        try:

            grPlanAValidar = send_message(
                build_message(gr, perf=ACL.request, sender=UserClient.uri, receiver=Planificador.uri,
                            msgcnt=get_count(),
                            content=contentResult), Planificador.address)

            plan = {"fechaIda": fechaIda, "fechaVuelta": fechaVuelta}

            for s, p, o in grPlanAValidar:
                if p == Ontologia.tematica:
                    plan['tematica'] =  o
                elif p == Ontologia.ciudad_destino:
                    plan['ciudad_destino'] =  o
                elif p == Ontologia.ciudad_origen:
                    plan['ciudad_origen'] =  o
                elif p == Ontologia.coste:
                    plan['coste'] =  o
                elif p == Ontologia.correo:
                    plan['correo'] =  o
                elif p == Ontologia.alojamiento:
                    plan['alojamiento'] =  o
                elif p == Ontologia.vuelo_ida:
                    plan['vuelo'] =  o
                elif p == Ontologia.actividades:
                    plan['actividades'] =  o
                elif p == Ontologia.vuelo:
                    plan["vuelo"] = urllib.parse.unquote(o)
                elif p == Ontologia.nomHotel:
                    plan["nomHotel"] = urllib.parse.unquote(o)
                elif p == Ontologia.linkHotel:
                    plan["linkHotel"] = urllib.parse.unquote(o)

            #plan["vuelo"] = "https://www.google.com/"
            return render_template('confirmar_y_pagar.html', plan=plan)

        except:
            return render_template('error_planificar.html')


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente
    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    """
    return


def tidyup():
    """
    Acciones previas a parar el agente
    """
    pass


def agentbehavior1():
    """
    Un comportamiento del agente
    :return:
    """
    logger.info("INICIANDO CLIENTE")

if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port, debug=True)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
