# -*- coding: utf-8 -*-
"""
filename: UserPersonalAgent
Agent que implementa la interacció amb l'usuari
"""
import random

import sys

import argparse
import socket
from multiprocessing import Process, Queue
from flask import Flask, render_template, request
from rdflib import Graph, Namespace, RDF, Literal, XSD

from PracticaTienda.utils.ACLMessages import get_agent_info, send_message, build_message, register_agent
from PracticaTienda.utils.Agent import Agent
from PracticaTienda.utils.FlaskServer import shutdown_server
from PracticaTienda.utils.Logging import config_logger
from PracticaTienda.utils.OntologyNamespaces import ECSDI, ACL

__author__ = 'amazdonde'

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
    port = 9018
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
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
VendedorExterno = Agent('VenderoExterno',
                                    agn.VendedorExterno,
                                    'http://%s:%d/comm' % (hostname, port),
                                    'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()

# Queue
queue = Queue()


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    return register_agent(VendedorExterno, DirectoryAgent, VendedorExterno.uri, get_count())


@app.route("/")
def browser_root():
    return render_template('Vendedor_main_page.html')


@app.route("/registrarProducto", methods=['GET', 'POST'])
def browser_registrarProducto():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    if request.method == 'GET':
        return render_template('registrarProductos.html')
    else:
        Marca = request.form['Marca']
        Nombre = request.form['Nombre']
        Modelo = request.form['Modelo']
        Precio = request.form['Precio']
        Peso = request.form['Peso']
        vendido = 0

        # Content of the message
        content = ECSDI['Registrar_productos_' + str(get_count())]

        # Graph creation
        gr = Graph()
        gr.add((content, RDF.type, ECSDI.Registrar_productos))

        # Anadir nuevo producto externo al grafo

        subjectProd = ECSDI['Producto_externo_' + str(random.randint(1, sys.float_info.max))]

        gr.add((subjectProd, RDF.type, ECSDI.Producto_externo))
        gr.add((subjectProd, ECSDI.Nombre, Literal(Nombre, datatype=XSD.string)))
        gr.add((subjectProd, ECSDI.Marca, Literal(Marca, datatype=XSD.string)))
        gr.add((subjectProd, ECSDI.Modelo, Literal(Modelo, datatype=XSD.string)))
        gr.add((subjectProd, ECSDI.Precio, Literal(Precio, datatype=XSD.float)))
        gr.add((subjectProd, ECSDI.Peso, Literal(Peso, datatype=XSD.float)))
        gr.add((subjectProd, ECSDI.Vendido, Literal(vendido)))

        gr.add((content, ECSDI.producto, subjectProd))

        publicador = get_agent_info(agn.AgentePublicador, DirectoryAgent, VendedorExterno, get_count())

        send_message(
            build_message(gr, perf=ACL.request, sender=VendedorExterno.uri, receiver=publicador.uri,
                          msgcnt=get_count(),
                          content=content), publicador.address)

        producto_registrado = {'Marca': request.form['Marca'], 'Nombre': request.form['Nombre'], 'Modelo': request.form['Modelo'],
               'Precio': request.form['Precio'], 'Peso': request.form['Peso']}

        return render_template('ProductoRegistrado.html', producto=producto_registrado)


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


def agent_behaviour(queue):
    """
    Agent Behaviour in a concurrent thread.
    :param queue: the queue
    :return: something
    """



if __name__ == '__main__':
    # ------------------------------------------------------------------------------------------------------
    # Run behaviors
    ab1 = Process(target=agent_behaviour, args=(queue,))
    ab1.start()

    # Run server
    app.run(host=hostname, port=port)

    # Wait behaviors
    ab1.join()
    print('The End')